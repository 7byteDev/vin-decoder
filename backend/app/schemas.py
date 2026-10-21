"""Pydantic-Modelle der oeffentlichen API.

Die API liefert *Schluessel* (z. B. ``make``, ``model_year``) und Rohwerte.
Die Uebersetzung nach EN/DE/TR passiert im Frontend, damit dieselbe Antwort
fuer alle Sprachen cachebar bleibt.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Lang = Literal["en", "de", "tr"]


class Alternative(BaseModel):
    value: Any
    confidence: float
    sources: list[str]


class FieldResult(BaseModel):
    value: Any
    confidence: float = Field(ge=0, le=1)
    sources: list[str]
    value_i18n: dict[str, str] | None = None
    alternatives: list[Alternative] = []
    conflict: bool = False


class VinStructure(BaseModel):
    """Rein strukturelle, deterministische Zerlegung der VIN."""

    wmi: str
    vds: str
    #: VIS nur bis Position 11 (Modelljahr + Werk); der Seriennummernblock
    #: wird maskiert, damit die Antwort kein Einzelfahrzeug identifiziert.
    vis_masked: str
    extended_wmi: str | None = None
    is_small_manufacturer: bool = False
    region_code: str | None = None
    region_name: str | None = None
    country: str | None = None
    country_code: str | None = None
    in_primary_focus: bool = False
    check_digit: str | None = None
    check_digit_expected: str | None = None
    check_digit_valid: bool | None = None
    check_digit_required: bool = False
    model_year_code: str | None = None
    model_year: int | None = None
    model_year_candidates: list[int] = []
    plant_code: str | None = None


class DecodeRequest(BaseModel):
    vin: str = Field(min_length=1, max_length=32)
    lang: Lang = "en"
    live: bool = True


class DecodeResponse(BaseModel):
    vin_masked: str
    status: Literal["ok", "partial"] = "ok"
    confidence: float = Field(ge=0, le=1)
    structure: VinStructure
    fields: dict[str, FieldResult]
    conflicts: list[str] = []
    warnings: list[str] = []
    sources_used: list[str] = []
    provider_errors: dict[str, str] = {}
    duration_ms: int = 0
    #: Konkrete Typengenehmigungen, auf die die VIN passt. Mehrere Treffer
    #: sind der Normalfall - eine VIN unterscheidet die Motorisierungen
    #: einer Baureihe nicht.
    matches: list[VehicleMatch] = []
    match_count: int = 0


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SourceInfo(BaseModel):
    key: str
    name: str
    url: str | None = None
    license: str | None = None
    license_ok: bool
    attribution: str | None = None
    reliability: float
    region_focus: list[str] = []
    last_import_at: str | None = None
    record_count: int = 0
    notes: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    live_source: bool
    mode: Literal["full", "structural_only"]


class StatsResponse(BaseModel):
    wmi_rows: int = 0
    wmi_codes: int = 0
    patterns: int = 0
    reference_vehicles: int = 0
    active_sources: int = 0
    lookups: int = 0
    database: bool = False


# ---------------------------------------------------------------------------
# Typengenehmigungen
# ---------------------------------------------------------------------------


class VehicleMatch(BaseModel):
    """Kurzfassung einer Typengenehmigung fuer die Trefferliste."""

    id: int
    approval_number: str | None = None
    make: str | None = None
    model: str | None = None
    variant: str | None = None
    year: int | None = None
    body_form: str | None = None
    fuel_type: str | None = None
    displacement_ccm: int | None = None
    power_kw: float | None = None
    power_ps: int | None = None
    transmission: str | None = None
    gears: int | None = None
    drive_type: str | None = None
    doors: int | None = None
    seats: int | None = None
    match_quality: float = 0.0
    matched_prefix: str | None = None


class SpecSection(BaseModel):
    """Ein Abschnitt der Detailansicht, wie ihn das ASTRA gliedert."""

    key: str
    label: str
    entries: dict[str, str]


class VehicleDetail(BaseModel):
    id: int
    approval_number: str | None = None
    approval_date: str | None = None
    eu_approval_number: str | None = None
    vin_patterns: list[str] = []

    make: str | None = None
    model: str | None = None
    variant: str | None = None
    manufacturer: str | None = None
    vehicle_kind: str | None = None
    vehicle_class: str | None = None
    body_form: str | None = None

    engine_make: str | None = None
    engine_model: str | None = None
    engine_code: str | None = None
    fuel_type: str | None = None
    displacement_ccm: int | None = None
    power_kw: float | None = None
    power_ps: int | None = None
    power_rpm: int | None = None
    torque_nm: int | None = None
    torque_rpm: int | None = None
    drive_type: str | None = None
    transmission: str | None = None
    gears: int | None = None

    doors: int | None = None
    seats_total: int | None = None
    top_speed_kmh: int | None = None
    length_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    wheelbase_mm: int | None = None
    weight_kg: int | None = None
    max_weight_kg: int | None = None

    #: Ausfuehrung, die die VIN in der Zuordnungstabelle auswaehlt
    variant_code: str | None = None
    #: Obergrenze je Feld, wenn die Typengenehmigung eine Spanne abdeckt
    #: (Laenge 5180-5320 mm). Nur gesetzt, wo sie ueber dem Basiswert liegt.
    ranges: dict[str, int] = {}

    sections: list[SpecSection] = []
    #: Markenlogo (Wikimedia Commons)
    logo: BrandLogo | None = None
    #: Frei lizenzierte Fotos der Baureihe (Wikimedia Commons)
    images: list[VehicleImage] = []
    consumption: list[ConsumptionRow] = []
    emissions: list[EmissionRow] = []
    source: str | None = None
    attribution: str | None = None


class ConsumptionRow(BaseModel):
    """Verbrauchswerte einer Getriebevariante."""

    fuel_type: str | None = None
    transmission: str | None = None
    efficiency_category: str | None = None
    consumption_l100: float | None = None
    co2_g_km: int | None = None
    consumption_wltp_l100: float | None = None
    co2_wltp_g_km: int | None = None
    electric_kwh100: float | None = None
    electric_range_km: int | None = None


class EmissionRow(BaseModel):
    """Emissionswerte einer Getriebevariante."""

    fuel_type: str | None = None
    transmission: str | None = None
    emission_code: str | None = None
    exhaust_code: str | None = None
    cylinders: int | None = None
    displacement_ccm: int | None = None
    power_kw: float | None = None
    pollutants: dict[str, str] = {}


class VehicleImage(BaseModel):
    """Frei lizenziertes Foto aus Wikimedia Commons."""

    file_key: str
    url: str
    thumb_url: str
    page_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    author: str | None = None
    description: str | None = None
    width: int | None = None
    height: int | None = None


class BrandLogo(BaseModel):
    """Markenlogo aus Wikimedia Commons.

    Logos sind Marken- und teils Urheberrecht. Angezeigt wird es zur
    Bezeichnung genau des Herstellers, dessen Fahrzeug daneben steht;
    Lizenz und Urheber werden mitgefuehrt.
    """

    url: str
    page_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    author: str | None = None


# ---------------------------------------------------------------------------
# Blaettern nach Marke
# ---------------------------------------------------------------------------


class BrandSummary(BaseModel):
    """Eine Marke in der Uebersicht."""

    make: str
    name: str
    slug: str
    vehicles: int
    models: int
    logo_url: str | None = None


class ModelSummary(BaseModel):
    """Ein Modell einer Marke."""

    model: str
    slug: str
    generations: int
    vehicles: int
    year_from: int | None = None
    year_to: int | None = None
    thumb_url: str | None = None


class GenerationSummary(BaseModel):
    """Eine Baureihengeneration mit Bauzeitraum und Bild."""

    platform: str
    slug: str
    year_from: int | None = None
    year_to: int | None = None
    vehicles: int
    image_url: str | None = None
    thumb_url: str | None = None


class GenerationVehicle(BaseModel):
    """Eine Zeile der Fahrzeugliste einer Generation.

    Technisch gleiche Typengenehmigungen sind zusammengefasst; ``approvals``
    sagt, wie viele es waren.
    """

    id: int
    model: str
    fuel_type: str | None = None
    power_kw: float | None = None
    power_ps: int | None = None
    displacement_ccm: int | None = None
    transmission: str | None = None
    gears: int | None = None
    drive_type: str | None = None
    body_form: str | None = None
    doors: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    approvals: int = 1
    approval_numbers: list[str] = []
