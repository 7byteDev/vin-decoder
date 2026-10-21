"""Provider: Abgleich gegen die eigene PostgreSQL-Datenbank.

Deckt Schritt 2 der Aufloesungskette ab (WMI, Herstellerregeln,
Referenzfahrzeuge). Jede Zeile bringt ihre Quelle mit, sodass die Engine
Uebereinstimmungen und Widersprueche zwischen Quellen bewerten kann.
"""

from __future__ import annotations

import re
import time
from typing import Any

from ..db import PATTERN_QUERY, VEHICLE_REFERENCE_QUERY, WMI_QUERY, Database
from ..decoder.structural import StructuralResult
from ..decoder.types import Attr, Candidate, ProviderResult


def chars_at(vin: str, positions: list[int]) -> str:
    """Zeichen an 1-basierten VIN-Positionen zusammensetzen."""
    return "".join(vin[p - 1] for p in positions if 1 <= p <= len(vin))


def pattern_matches(vin: str, positions: list[int], match_type: str, pattern: str) -> bool:
    value = chars_at(vin, positions)
    if len(value) != len(positions):
        return False
    if match_type == "regex":
        try:
            return re.fullmatch(pattern, value) is not None
        except re.error:
            return False
    return value == pattern


def _year_applies(model_year: int | None, year_from: int | None, year_to: int | None) -> bool:
    if year_from is None and year_to is None:
        return True
    if model_year is None:
        return True  # ohne Jahr nicht ausschliessen, nur schwaecher gewichten
    if year_from is not None and model_year < year_from:
        return False
    return not (year_to is not None and model_year > year_to)


#: Spalte in vehicles_reference -> Attributname
_REFERENCE_COLUMNS: dict[str, str] = {
    "make": Attr.MAKE,
    "model": Attr.MODEL,
    "series": Attr.SERIES,
    "trim": Attr.TRIM,
    "body_class": Attr.BODY_CLASS,
    "vehicle_type": Attr.VEHICLE_TYPE,
    "fuel_type": Attr.FUEL_TYPE,
    "engine_displacement_l": Attr.ENGINE_DISPLACEMENT_L,
    "engine_cylinders": Attr.ENGINE_CYLINDERS,
    "engine_power_kw": Attr.ENGINE_POWER_KW,
    "drive_type": Attr.DRIVE_TYPE,
    "transmission": Attr.TRANSMISSION,
    "plant_country": Attr.PLANT_COUNTRY,
    "plant_city": Attr.PLANT_CITY,
    "plant_company": Attr.PLANT_COMPANY,
}


class DatabaseProvider:
    """Liest alle DB-gestuetzten Kandidaten fuer eine VIN."""

    key = "vindb"

    def __init__(self, db: Database) -> None:
        self._db = db

    async def fetch(self, structural: StructuralResult) -> ProviderResult:
        started = time.perf_counter()
        if not self._db.available:
            return ProviderResult(source=self.key, used=False, error="database_unavailable")

        codes = structural.wmi_lookup_codes
        candidates: list[Candidate] = []
        try:
            candidates += await self._wmi_candidates(codes)
            candidates += await self._pattern_candidates(codes, structural)
            candidates += await self._reference_candidates(codes, structural)
        except Exception as exc:  # pragma: no cover - Laufzeitfehler der DB
            return ProviderResult(source=self.key, used=False, error=str(exc))

        return ProviderResult(
            source=self.key,
            candidates=candidates,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    # -- Teilabfragen -------------------------------------------------------

    async def _wmi_candidates(self, codes: list[str]) -> list[Candidate]:
        rows = await self._db.fetch(WMI_QUERY, codes)
        out: list[Candidate] = []
        for row in rows:
            src = f"{self.key}:wmi:{row['source_key']}"
            base = float(row["confidence"]) * float(row["reliability"])
            # Spezifitaet: 6-stellige (erweiterte) WMI > 3-stellige > 2-stelliges Praefix
            if len(row["code"]) == 6:
                base = min(0.99, base * 1.1)
            elif len(row["code"]) == 2:
                base *= 0.85
            out.append(Candidate(Attr.MANUFACTURER, row["manufacturer_name"], src, round(base, 4)))
            if row["common_name"]:
                out.append(Candidate(Attr.MAKE, row["common_name"], src, round(base, 4)))
            if row["country"]:
                out.append(Candidate(Attr.COUNTRY, row["country"], src, round(base * 0.9, 4)))
            if row["country_code"]:
                out.append(
                    Candidate(Attr.COUNTRY_CODE, row["country_code"], src, round(base * 0.9, 4))
                )
            if row["vehicle_type"]:
                out.append(
                    Candidate(Attr.VEHICLE_TYPE, row["vehicle_type"], src, round(base * 0.85, 4))
                )
        return out

    async def _pattern_candidates(
        self, codes: list[str], structural: StructuralResult
    ) -> list[Candidate]:
        rows = await self._db.fetch(PATTERN_QUERY, codes)
        out: list[Candidate] = []
        for row in rows:
            positions = [int(p) for p in row["positions"]]
            if not pattern_matches(
                structural.vin, positions, row["match_type"], row["pattern"]
            ):
                continue
            if not _year_applies(structural.model_year, row["year_from"], row["year_to"]):
                continue
            confidence = float(row["confidence"]) * float(row["reliability"])
            if row["wmi_code"] == "*":
                confidence *= 0.7  # generische Regel ist schwaecher als eine WMI-spezifische
            if structural.model_year is None and (row["year_from"] or row["year_to"]):
                confidence *= 0.85
            out.append(
                Candidate(
                    attribute=row["attribute"],
                    value=row["value"],
                    source=f"{self.key}:pattern:{row['source_key']}",
                    confidence=round(min(0.99, confidence), 4),
                    value_i18n=dict(row["value_i18n"]) if row["value_i18n"] else None,
                )
            )
        return out

    async def _reference_candidates(
        self, codes: list[str], structural: StructuralResult
    ) -> list[Candidate]:
        rows = await self._db.fetch(
            VEHICLE_REFERENCE_QUERY, codes, structural.model_year, structural.vin
        )
        out: list[Candidate] = []
        for row in rows:
            src = f"{self.key}:reference:{row['source_key']}"
            # laengeres Praefix = spezifischerer Treffer
            specificity = min(1.0, 0.6 + 0.05 * (len(row["vin_prefix"]) - 3))
            base = float(row["confidence"]) * float(row["reliability"]) * specificity
            for column, attribute in _REFERENCE_COLUMNS.items():
                value: Any = row[column]
                if value in (None, ""):
                    continue
                if column in ("engine_displacement_l",):
                    value = float(value)
                out.append(Candidate(attribute, value, src, round(min(0.99, base), 4)))
            if row["model_year"]:
                out.append(
                    Candidate(Attr.MODEL_YEAR, int(row["model_year"]), src, round(base * 0.9, 4))
                )
        return out
