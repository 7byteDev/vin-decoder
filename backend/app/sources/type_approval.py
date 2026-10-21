"""Provider: Typengenehmigungen (Schweizer TARGA-Daten).

Das ist die Quelle fuer die eigentlichen Technikdaten europaeischer
Fahrzeuge - Motor, Leistung, Getriebe, Abmessungen, Gewichte.

Der Weg dahin fuehrt ueber das VIN-Muster ("Vorziffer") der Genehmigung.
Ein Muster trifft praktisch nie genau ein Fahrzeug, sondern eine Menge von
Motorisierungen derselben Baureihe. Statt daraus willkuerlich eine
auszuwaehlen, macht dieser Provider zweierlei:

* Attribute, in denen sich **alle** Treffer einig sind (etwa die Marke),
  werden mit hoher Konfidenz gemeldet.
* Attribute, in denen sie sich unterscheiden (etwa die Leistung), werden
  mit der Haeufigkeit gewichtet - die Engine zeigt sie dann samt
  Alternativen an.

Zusaetzlich liefert er die Trefferliste selbst, damit die Oberflaeche die
konkreten Varianten zur Auswahl anbieten kann.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from typing import Any

from ..db import TYPE_APPROVAL_QUERY, Database
from ..decoder.structural import StructuralResult
from ..decoder.types import Attr, Candidate, ProviderResult


def specificity(fixed_chars: int) -> float:
    """Wie spezifisch ist ein VIN-Muster?

    Gezaehlt werden die FESTEN Zeichen, nicht die Praefixlaenge. Beim
    VW-Konzern steht der Typschluessel an Position 7-8, das Muster lautet
    also z. B. "TMB...1U........." - Praefix "TMB" (3 Zeichen), aber
    fuenf feste Stellen. Nach der Praefixlaenge gemessen waere so ein
    Treffer so unspezifisch wie "irgendein Skoda", tatsaechlich meint er
    eine konkrete Baureihe.
    """
    if fixed_chars >= 11:
        return 0.95
    if fixed_chars >= 9:
        return 0.88
    if fixed_chars >= 7:
        return 0.80
    if fixed_chars >= 6:
        return 0.72
    if fixed_chars >= 5:
        return 0.66
    if fixed_chars >= 4:
        return 0.45
    return 0.25


#: Spalte -> Attribut. Nur Werte, die fuer den Decoder relevant sind;
#: die vollstaendigen Daten haengen an der Detailansicht.
ATTRIBUTE_COLUMNS: dict[str, str] = {
    "make": Attr.MAKE,
    "model": Attr.SERIES,
    "manufacturer": Attr.MANUFACTURER,
    "body_form": Attr.BODY_CLASS,
    "vehicle_kind": Attr.VEHICLE_TYPE,
    "fuel_type": Attr.FUEL_TYPE,
    "engine_code": Attr.ENGINE_MODEL,
    "displacement_ccm": Attr.ENGINE_DISPLACEMENT_L,
    "power_kw": Attr.ENGINE_POWER_KW,
    "drive_type": Attr.DRIVE_TYPE,
    "transmission": Attr.TRANSMISSION,
    "doors": Attr.DOORS,
    "seats_total": Attr.SEATS,
}

#: TARGA schreibt Marken teils abgekuerzt oder in Versalien. Fuer die
#: Anzeige und den Abgleich mit anderen Quellen wird die uebliche
#: Schreibweise verwendet.
MAKE_ALIASES = {
    "VW": "Volkswagen",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "ALFA ROMEO": "Alfa Romeo",
    "LAND ROVER": "Land Rover",
    "ROLLS ROYCE": "Rolls-Royce",
    "SKODA": "Škoda",
    "CITROEN": "Citroën",
}


def normalize_make(make: str | None) -> str | None:
    """'VW' -> 'Volkswagen', 'AUDI' -> 'Audi'."""
    if not make:
        return None
    cleaned = " ".join(make.strip().split())
    alias = MAKE_ALIASES.get(cleaned.upper())
    if alias:
        return alias
    # Versalien in Titelschreibweise, Bindestriche beachten
    if cleaned.isupper():
        return "-".join(part.capitalize() for part in cleaned.split("-"))
    return cleaned


#: Wie viele Jahre vor dem Modelljahr darf eine Genehmigung erteilt worden
#: sein? Typgenehmigungen gelten ueber die gesamte Bauzeit einer Baureihe.
APPROVAL_MAX_AGE_YEARS = 12
MATCH_LIMIT = 400


class TypeApprovalProvider:
    """Sucht Typengenehmigungen zur VIN und verdichtet sie zu Kandidaten."""

    key = "targa"

    def __init__(self, db: Database, *, match_limit: int = MATCH_LIMIT) -> None:
        self._db = db
        self._match_limit = match_limit

    async def fetch(self, structural: StructuralResult) -> ProviderResult:
        started = time.perf_counter()
        if not self._db.available:
            return ProviderResult(source=self.key, used=False, error="database_unavailable")

        prefixes = [structural.vin[:n] for n in range(2, 18)]
        try:
            rows = await self._db.fetch(
                TYPE_APPROVAL_QUERY, prefixes, self._match_limit, structural.vin
            )
        except Exception as exc:  # pragma: no cover - Laufzeitfehler der DB
            return ProviderResult(source=self.key, used=False, error=str(exc))

        # Der Musterabgleich ist bereits in SQL passiert.
        matches = self._filter_by_year(list(rows), structural.model_year)
        if not matches:
            return ProviderResult(source=self.key, candidates=[], matches=[])

        reliability = float(matches[0]["reliability"])
        base = specificity(int(matches[0]["fixed_chars"])) * reliability

        return ProviderResult(
            source=self.key,
            candidates=self._candidates(matches, base),
            matches=[summarize(row) for row in matches],
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    # -- Filter -------------------------------------------------------------

    @staticmethod
    def _filter_by_year(rows: list[Any], model_year: int | None) -> list[Any]:
        """Genehmigungen ausschliessen, die zum Modelljahr nicht passen.

        Eine Genehmigung wird vor Produktionsbeginn erteilt und gilt dann
        ueber die Bauzeit. Sie darf also aelter sein als das Fahrzeug, aber
        nicht wesentlich juenger.
        """
        if model_year is None:
            return rows
        kept = []
        for row in rows:
            year = row["model_year_from"]
            if year is None or model_year - APPROVAL_MAX_AGE_YEARS <= year <= model_year + 1:
                kept.append(row)
        return kept or rows

    # -- Verdichtung --------------------------------------------------------

    @staticmethod
    def model_family(model: str | None) -> str | None:
        """"A4 Avant 2.0TDI" -> "A4", "Octavia C 2.0TDI" -> "Octavia".

        TARGA schreibt die Motorisierung in den Modellnamen. Fuer die
        Baureihe ist nur der vordere Teil interessant - und nur so sind
        sich die Treffer einig genug, dass eine belastbare Konfidenz
        herauskommt. Der vollstaendige Name bleibt als Baureihe erhalten.
        """
        if not model:
            return None
        first = model.strip().split()
        if not first:
            return None
        family = first[0]
        # zweites Wort mitnehmen, wenn es kein Motor-/Ausstattungskuerzel ist
        second_is_name = (
            len(first) > 1
            and first[1].isalpha()
            and len(first[1]) > 2
            and not re.match(r"^(av|sb|qu|quattro|combi|variant|cabrio|coupe)", first[1], re.I)
        )
        if second_is_name:
            family = f"{family} {first[1]}"
        return family

    def _candidates(self, rows: list[Any], base: float) -> list[Candidate]:
        """Aus n Treffern je Attribut Kandidaten mit Haeufigkeitsgewicht."""
        total = len(rows)
        out: list[Candidate] = []

        # Baureihe getrennt zaehlen - sonst zerfaellt sie in Motorvarianten
        families: Counter = Counter()
        for row in rows:
            family = self.model_family(row["model"])
            if family:
                families[family] += 1
        for family, count in families.most_common(3):
            agreement = count / total
            out.append(
                Candidate(
                    attribute=Attr.MODEL,
                    value=family,
                    source=self.key,
                    confidence=round(min(0.97, base * (0.45 + 0.55 * agreement)), 4),
                    note=f"{count}/{total} Typengenehmigungen",
                )
            )

        for column, attribute in ATTRIBUTE_COLUMNS.items():
            counter: Counter = Counter()
            for row in rows:
                value = row[column]
                if value in (None, ""):
                    continue
                if column == "make":
                    value = normalize_make(value)
                elif column == "displacement_ccm":
                    value = round(float(value) / 1000.0, 1)
                elif column == "power_kw":
                    value = int(round(float(value)))
                counter[value] += 1
            if not counter:
                continue

            # Einigkeit unter den Treffern staerkt, Streuung schwaecht
            for value, count in counter.most_common(3):
                agreement = count / total
                confidence = base * (0.45 + 0.55 * agreement)
                out.append(
                    Candidate(
                        attribute=attribute,
                        value=value,
                        source=self.key,
                        confidence=round(min(0.97, confidence), 4),
                        note=f"{count}/{total} Typengenehmigungen",
                    )
                )
        return out


def summarize(row: Any) -> dict[str, Any]:
    """Kurzfassung einer Genehmigung fuer die Trefferliste."""
    power_kw = float(row["power_kw"]) if row["power_kw"] is not None else None
    return {
        "id": row["id"],
        "approval_number": row["approval_number"],
        "make": normalize_make(row["make"]),
        "model": row["model"],
        "variant": row["variant"],
        "year": row["model_year_from"],
        "body_form": row["body_form"],
        "fuel_type": row["fuel_type"],
        "displacement_ccm": row["displacement_ccm"],
        "power_kw": power_kw,
        "power_ps": round(power_kw * 1.35962) if power_kw else None,
        "transmission": row["transmission"],
        "gears": row["gears"],
        "drive_type": row["drive_type"],
        "doors": row["doors"],
        "seats": row["seats_total"],
        "match_quality": round(specificity(int(row["fixed_chars"])), 2),
        "matched_prefix": row["pattern"],
    }
