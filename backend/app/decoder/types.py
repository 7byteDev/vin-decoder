"""Gemeinsame Typen der Decoder-Pipeline.

Der Decoder liefert bewusst *keine* einzelne Blackbox-Antwort, sondern pro
Attribut eine Menge von Kandidaten mit Quelle und Konfidenz. Das Zusammen-
fuehren passiert erst in ``engine.merge_candidates`` - Widersprueche zwischen
Quellen bleiben dabei sichtbar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Attr(StrEnum):
    """Kanonische Attributnamen. Zugleich die i18n-Schluessel im Frontend."""

    COUNTRY = "country"
    COUNTRY_CODE = "country_code"
    REGION = "region"
    MANUFACTURER = "manufacturer"
    MAKE = "make"
    MODEL = "model"
    SERIES = "series"
    TRIM = "trim"
    MODEL_YEAR = "model_year"
    VEHICLE_TYPE = "vehicle_type"
    BODY_CLASS = "body_class"
    FUEL_TYPE = "fuel_type"
    ENGINE_DISPLACEMENT_L = "engine_displacement_l"
    ENGINE_CYLINDERS = "engine_cylinders"
    ENGINE_POWER_KW = "engine_power_kw"
    ENGINE_MODEL = "engine_model"
    DRIVE_TYPE = "drive_type"
    TRANSMISSION = "transmission"
    DOORS = "doors"
    SEATS = "seats"
    PLANT_CODE = "plant_code"
    PLANT_CITY = "plant_city"
    PLANT_COUNTRY = "plant_country"
    PLANT_COMPANY = "plant_company"


#: Attribute, die in die Gesamtkonfidenz einfliessen, mit ihrem Gewicht.
CORE_ATTRIBUTE_WEIGHTS: dict[str, float] = {
    Attr.COUNTRY: 1.0,
    Attr.MANUFACTURER: 2.0,
    Attr.MAKE: 2.0,
    Attr.MODEL: 3.0,
    Attr.MODEL_YEAR: 2.0,
    Attr.VEHICLE_TYPE: 1.0,
}


@dataclass(slots=True)
class Candidate:
    """Ein Wertvorschlag genau einer Quelle fuer genau ein Attribut."""

    attribute: str
    value: object
    source: str
    confidence: float
    value_i18n: dict[str, str] | None = None
    note: str | None = None

    @property
    def normalized(self) -> str:
        """Vergleichsform, um Uebereinstimmung zwischen Quellen zu erkennen."""
        if self.value is None:
            return ""
        if isinstance(self.value, float) and self.value.is_integer():
            return str(int(self.value))
        return " ".join(str(self.value).strip().casefold().split())


@dataclass(slots=True)
class ResolvedField:
    """Zusammengefuehrtes Ergebnis fuer ein Attribut."""

    attribute: str
    value: object
    confidence: float
    sources: list[str]
    value_i18n: dict[str, str] | None = None
    alternatives: list[dict] = field(default_factory=list)
    conflict: bool = False


@dataclass(slots=True)
class ProviderResult:
    """Rueckgabe einer Datenquelle innerhalb der Aufloesungskette."""

    source: str
    candidates: list[Candidate] = field(default_factory=list)
    used: bool = True
    error: str | None = None
    duration_ms: int | None = None
    #: Konkrete Datensaetze hinter den Kandidaten (z. B. Typengenehmigungen).
    #: Die Oberflaeche bietet sie zur Auswahl an, wenn eine VIN mehrere
    #: Motorisierungen derselben Baureihe treffen kann.
    matches: list[dict] = field(default_factory=list)
