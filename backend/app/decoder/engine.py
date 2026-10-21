"""Aufloesungskette und Konfidenz-Scoring.

Reihenfolge laut Projektplan (Abschnitt 3):

    1. strukturelle Decodierung   - deterministisch, funktioniert immer
    2. Abgleich gegen die eigene DB (WMI, Herstellerregeln, Referenzfahrzeuge)
    3. bei Luecken: Live-Nachfrage bei einer freien API (NHTSA vPIC)
    4. Zusammenfuehren mit Quellenangabe und Konfidenz; Widersprueche
       werden ausgewiesen statt stillschweigend aufgeloest

Die Provider sind austauschbar (Protokoll ``Provider``), damit spaetere
Quellen ohne Eingriff in die Engine ergaenzt werden koennen.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Protocol, runtime_checkable

from .structural import StructuralResult, VinFormatError, decode_structural, mask_vin
from .types import CORE_ATTRIBUTE_WEIGHTS, Attr, Candidate, ProviderResult, ResolvedField

logger = logging.getLogger(__name__)

#: Ab diesem Verhaeltnis Zweitplatzierter/Erstplatzierter gilt ein Attribut
#: als widerspruechlich und wird im Ergebnis markiert.
CONFLICT_RATIO_THRESHOLD = 0.35

#: Attribute, deren Fehlen eine Live-Nachfrage rechtfertigt.
LIVE_TRIGGER_ATTRIBUTES = (Attr.MAKE, Attr.MODEL, Attr.MANUFACTURER)


@runtime_checkable
class Provider(Protocol):
    """Eine Datenquelle in der Aufloesungskette."""

    key: str

    async def fetch(self, structural: StructuralResult) -> ProviderResult: ...


# ---------------------------------------------------------------------------
# Schritt 1: strukturelle Kandidaten
# ---------------------------------------------------------------------------


def structural_candidates(s: StructuralResult) -> list[Candidate]:
    src = "structural"
    out: list[Candidate] = []
    if s.country:
        out.append(Candidate(Attr.COUNTRY, s.country, src, 0.95))
        out.append(Candidate(Attr.COUNTRY_CODE, s.country_code, src, 0.95))
    if s.region_name:
        out.append(Candidate(Attr.REGION, s.region_name, src, 0.95))
    if s.model_year and s.model_year_confidence > 0:
        out.append(Candidate(Attr.MODEL_YEAR, s.model_year, src, s.model_year_confidence))
    if s.plant_code:
        out.append(Candidate(Attr.PLANT_CODE, s.plant_code, src, 0.9))
    return out


# ---------------------------------------------------------------------------
# Schritt 4: Zusammenfuehren
# ---------------------------------------------------------------------------


def _group_score(confidences: list[float]) -> float:
    """Noisy-OR: unabhaengige Quellen, die dasselbe sagen, verstaerken sich."""
    inverse = 1.0
    for c in sorted(confidences, reverse=True):
        inverse *= 1.0 - max(0.0, min(1.0, c))
    return round(min(0.99, 1.0 - inverse), 4)


def merge_candidates(candidates: list[Candidate]) -> dict[str, ResolvedField]:
    """Kandidaten je Attribut zu einem Ergebnis mit Konfidenz verdichten."""
    by_attribute: dict[str, list[Candidate]] = {}
    for cand in candidates:
        if cand.value is None or cand.normalized == "":
            continue
        by_attribute.setdefault(cand.attribute, []).append(cand)

    resolved: dict[str, ResolvedField] = {}
    for attribute, items in by_attribute.items():
        groups: dict[str, list[Candidate]] = {}
        for cand in items:
            groups.setdefault(cand.normalized, []).append(cand)

        scored: list[tuple[float, str, list[Candidate]]] = []
        for norm, group in groups.items():
            best_per_source: dict[str, float] = {}
            for cand in group:
                best_per_source[cand.source] = max(
                    best_per_source.get(cand.source, 0.0), cand.confidence
                )
            scored.append((_group_score(list(best_per_source.values())), norm, group))
        scored.sort(key=lambda t: (-t[0], t[1]))

        winner_score, _, winner_group = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        ratio = runner_up / winner_score if winner_score else 0.0
        final_score = round(winner_score * (1.0 - 0.4 * min(1.0, ratio)), 4)

        # innerhalb der Gewinnergruppe die zuverlaessigste Auspraegung nehmen
        best = max(winner_group, key=lambda c: c.confidence)
        alternatives = [
            {
                "value": grp[0].value,
                "confidence": score,
                "sources": sorted({c.source for c in grp}),
            }
            for score, _, grp in scored[1:4]
        ]

        resolved[attribute] = ResolvedField(
            attribute=attribute,
            value=best.value,
            confidence=final_score,
            sources=sorted({c.source for c in winner_group}),
            value_i18n=next((c.value_i18n for c in winner_group if c.value_i18n), None),
            alternatives=alternatives,
            conflict=ratio > CONFLICT_RATIO_THRESHOLD,
        )
    return resolved


def overall_confidence(fields: dict[str, ResolvedField], s: StructuralResult) -> float:
    """Gesamtkonfidenz aus Abdeckung und Einzelkonfidenzen der Kernattribute."""
    total_weight = sum(CORE_ATTRIBUTE_WEIGHTS.values())
    weighted = 0.0
    covered = 0.0
    for attribute, weight in CORE_ATTRIBUTE_WEIGHTS.items():
        field = fields.get(attribute)
        if field is None:
            continue
        covered += weight
        weighted += weight * field.confidence
    if covered == 0:
        return 0.0

    quality = weighted / covered           # wie sicher ist das, was wir haben
    coverage = (covered / total_weight) ** 0.5  # wie viel davon haben wir ueberhaupt
    score = quality * coverage

    # Pruefziffer nur dort werten, wo sie verbindlich ist
    if s.check_digit_required and s.check_digit_valid is False:
        score *= 0.55
    elif s.check_digit_required and s.check_digit_valid:
        score = min(1.0, score * 1.05)
    if any(f.conflict for f in fields.values()):
        score *= 0.9
    return round(max(0.0, min(0.99, score)), 4)


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------


class DecodeOutcome:
    """Ergebnis eines vollstaendigen Decodier-Laufs (interne Form)."""

    __slots__ = (
        "structural",
        "fields",
        "confidence",
        "warnings",
        "sources_used",
        "provider_errors",
        "duration_ms",
        "matches",
    )

    def __init__(
        self,
        structural: StructuralResult,
        fields: dict[str, ResolvedField],
        confidence: float,
        warnings: list[str],
        sources_used: list[str],
        provider_errors: dict[str, str],
        duration_ms: int,
        matches: list[dict] | None = None,
    ) -> None:
        self.structural = structural
        self.fields = fields
        self.confidence = confidence
        self.warnings = warnings
        self.sources_used = sources_used
        self.provider_errors = provider_errors
        self.duration_ms = duration_ms
        self.matches = matches or []

    @property
    def conflicts(self) -> list[str]:
        return sorted(a for a, f in self.fields.items() if f.conflict)

    @property
    def vin_masked(self) -> str:
        return mask_vin(self.structural.vin)


async def decode(
    vin: str,
    *,
    db_providers: list[Provider] | None = None,
    live_providers: list[Provider] | None = None,
    allow_live: bool = True,
) -> DecodeOutcome:
    """VIN decodieren. Wirft ``VinFormatError`` bei formal ungueltiger Eingabe."""
    started = time.perf_counter()
    structural = decode_structural(vin)

    candidates = structural_candidates(structural)
    warnings = list(structural.warnings)
    sources_used = ["structural"]
    errors: dict[str, str] = {}
    matches: list[dict] = []

    async def run(providers: list[Provider]) -> None:
        if not providers:
            return
        results = await asyncio.gather(
            *(p.fetch(structural) for p in providers), return_exceptions=True
        )
        for provider, result in zip(providers, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("provider %s failed: %s", provider.key, result)
                errors[provider.key] = str(result)
                continue
            if result.error:
                errors[result.source] = result.error
            if result.matches:
                matches.extend(result.matches)
            if result.candidates:
                candidates.extend(result.candidates)
                if result.source not in sources_used:
                    sources_used.append(result.source)

    await run(db_providers or [])

    merged = merge_candidates(candidates)
    gaps = [a for a in LIVE_TRIGGER_ATTRIBUTES if a not in merged or merged[a].confidence < 0.6]
    if allow_live and gaps and live_providers:
        await run(live_providers)
        merged = merge_candidates(candidates)
        warnings.append("live_lookup_used")

    confidence = overall_confidence(merged, structural)
    if not merged.get(Attr.MAKE) and not merged.get(Attr.MANUFACTURER):
        warnings.append("manufacturer_unknown")

    return DecodeOutcome(
        structural=structural,
        fields=merged,
        confidence=confidence,
        warnings=sorted(set(warnings)),
        sources_used=sources_used,
        provider_errors=errors,
        duration_ms=int((time.perf_counter() - started) * 1000),
        matches=matches,
    )


__all__ = [
    "DecodeOutcome",
    "Provider",
    "VinFormatError",
    "decode",
    "merge_candidates",
    "overall_confidence",
    "structural_candidates",
]
