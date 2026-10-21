"""HTTP-Endpunkte der VIN-Decoder-API."""

from __future__ import annotations

import base64
import json
import logging
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query, Request
from fastapi.responses import Response

from ..db import (
    BRAND_LOGO_QUERY,
    BRAND_MODELS_QUERY,
    BRANDS_QUERY,
    CATALOG_GALLERY_FOR_APPROVAL,
    CATALOG_GALLERY_IMAGE,
    CATALOG_GENERATION_IMAGE,
    CATALOG_IMAGE_FOR_APPROVAL,
    CATALOG_MODEL_IMAGE,
    GENERATION_VEHICLES_QUERY,
    LOG_INSERT,
    MODEL_GENERATIONS_QUERY,
    RECENT_LOOKUPS_QUERY,
    SOURCES_QUERY,
    STATS_QUERY,
    STORED_IMAGE_QUERY,
    TYPE_APPROVAL_DETAIL_QUERY,
    TYPE_APPROVAL_EXTRAS_QUERY,
    VEHICLE_IMAGES_QUERY,
)
from ..decoder.constants import COUNTRY_RANGES, MODEL_YEAR_CODES, REGIONS
from ..decoder.engine import DecodeOutcome, decode
from ..decoder.structural import decode_structural, lookup_region
from ..decoder.types import Attr
from ..decoder.variant import resolve as resolve_variant
from ..schemas import (
    BrandLogo,
    BrandSummary,
    ConsumptionRow,
    DecodeRequest,
    DecodeResponse,
    EmissionRow,
    ErrorResponse,
    FieldResult,
    GenerationSummary,
    GenerationVehicle,
    HealthResponse,
    ModelSummary,
    SourceInfo,
    SpecSection,
    StatsResponse,
    VehicleDetail,
    VehicleImage,
    VehicleMatch,
    VinStructure,
)
from ..sources.type_approval import normalize_make

logger = logging.getLogger(__name__)
router = APIRouter()

VERSION = "1.0.0"


def _to_response(outcome: DecodeOutcome) -> DecodeResponse:
    s = outcome.structural
    fields = {
        name: FieldResult(
            value=f.value,
            confidence=f.confidence,
            sources=f.sources,
            value_i18n=f.value_i18n,
            alternatives=f.alternatives,
            conflict=f.conflict,
        )
        for name, f in outcome.fields.items()
    }
    complete = all(fields.get(a) for a in (Attr.MAKE, Attr.MODEL, Attr.MODEL_YEAR))
    return DecodeResponse(
        vin_masked=outcome.vin_masked,
        status="ok" if complete and outcome.confidence >= 0.5 else "partial",
        confidence=outcome.confidence,
        structure=VinStructure(
            wmi=s.wmi,
            vds=s.vds,
            vis_masked=s.vis[:2] + "XXXXXX",
            extended_wmi=s.extended_wmi,
            is_small_manufacturer=s.is_small_manufacturer,
            region_code=s.region_code,
            region_name=s.region_name,
            country=s.country,
            country_code=s.country_code,
            in_primary_focus=s.in_primary_focus,
            check_digit=s.check_digit,
            check_digit_expected=s.check_digit_expected,
            check_digit_valid=s.check_digit_valid,
            check_digit_required=s.check_digit_required,
            model_year_code=s.model_year_code,
            model_year=s.model_year,
            model_year_candidates=s.model_year_candidates,
            plant_code=s.plant_code,
        ),
        fields=fields,
        matches=[VehicleMatch(**m) for m in outcome.matches[:60]],
        match_count=len(outcome.matches),
        conflicts=outcome.conflicts,
        warnings=outcome.warnings,
        sources_used=outcome.sources_used,
        provider_errors=outcome.provider_errors,
        duration_ms=outcome.duration_ms,
    )


def _field_text(outcome: DecodeOutcome, attribute: str) -> str | None:
    field = outcome.fields.get(attribute)
    return str(field.value) if field and field.value is not None else None


async def _log_lookup(request: Request, outcome: DecodeOutcome, lang: str) -> None:
    """Anfrage protokollieren - maskiert, ohne IP, ohne Nutzerbezug."""
    app = request.app
    if not app.state.settings.log_lookups or not app.state.db.available:
        return
    try:
        await app.state.db.execute(
            LOG_INSERT,
            outcome.vin_masked,
            outcome.structural.wmi,
            outcome.structural.model_year,
            "ok" if outcome.confidence >= 0.5 else "partial",
            outcome.confidence,
            outcome.sources_used,
            json.dumps(outcome.conflicts),
            outcome.duration_ms,
            lang,
            _field_text(outcome, Attr.MAKE),
            _field_text(outcome, Attr.MODEL),
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("lookup log failed: %s", exc)


async def _decode(request: Request, vin: str, live: bool) -> DecodeOutcome:
    app = request.app
    return await decode(
        vin,
        db_providers=app.state.db_providers,
        live_providers=app.state.live_providers,
        allow_live=live and app.state.settings.enable_live_nhtsa,
    )


@router.get(
    "/decode/{vin}",
    response_model=DecodeResponse,
    responses={422: {"model": ErrorResponse}},
    summary="VIN decodieren",
)
async def decode_get(
    request: Request,
    background: BackgroundTasks,
    vin: str = Path(min_length=1, max_length=32, description="17-stellige VIN"),
    lang: str = Query("en", pattern="^(en|de|tr)$"),
    live: bool = Query(True, description="Live-Nachfrage bei freien APIs erlauben"),
):
    outcome = await _decode(request, vin, live)
    background.add_task(_log_lookup, request, outcome, lang)
    return _to_response(outcome)


@router.post(
    "/decode",
    response_model=DecodeResponse,
    responses={422: {"model": ErrorResponse}},
    summary="VIN decodieren (POST)",
)
async def decode_post(request: Request, payload: DecodeRequest, background: BackgroundTasks):
    outcome = await _decode(request, payload.vin, payload.live)
    background.add_task(_log_lookup, request, outcome, payload.lang)
    return _to_response(outcome)


@router.get("/sources", response_model=list[SourceInfo], summary="Genutzte Datenquellen")
async def list_sources(request: Request) -> list[SourceInfo]:
    rows = await request.app.state.db.fetch(SOURCES_QUERY)
    return [
        SourceInfo(
            key=r["key"],
            name=r["name"],
            url=r["url"],
            license=r["license"],
            license_ok=r["license_ok"],
            attribution=r["attribution"],
            reliability=float(r["reliability"]),
            region_focus=list(r["region_focus"]),
            last_import_at=r["last_import_at"].isoformat() if r["last_import_at"] else None,
            record_count=r["record_count"],
            notes=r["notes"],
        )
        for r in rows
    ]


@router.get("/stats", response_model=StatsResponse, summary="Datenbestand")
async def stats(request: Request) -> StatsResponse:
    db = request.app.state.db
    if not db.available:
        return StatsResponse(database=False)
    row = await db.fetchrow(STATS_QUERY)
    return StatsResponse(**dict(row), database=True) if row else StatsResponse(database=True)


@router.get("/attributes", summary="Attributschluessel fuer die Uebersetzung")
async def attributes() -> dict[str, list[str]]:
    return {"attributes": [a.value for a in Attr]}


@router.get("/health", response_model=HealthResponse, summary="Health-Check", tags=["ops"])
async def health(request: Request) -> HealthResponse:
    app = request.app
    db_ok = app.state.db.available and await app.state.db.healthy()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=VERSION,
        database=db_ok,
        live_source=app.state.settings.enable_live_nhtsa,
        mode="full" if db_ok else "structural_only",
    )


# ---------------------------------------------------------------------------
# Typengenehmigungen: Trefferliste und Detailansicht
# ---------------------------------------------------------------------------

#: Abschnitte der Detailansicht in der Reihenfolge, in der sie angezeigt
#: werden. Die Schluessel sind stabil, die Beschriftung uebersetzt das
#: Frontend; ``label`` traegt den Originaltitel des ASTRA als Rueckfall.
SECTION_ORDER = [
    ("datenblatt", "Datenblatt"),
    ("hersteller_typ", "Hersteller-Typ"),
    ("fahrgestell", "Fahrgestell"),
    ("motor", "Motor"),
    ("abmessungen", "Ausrüstung-Abmessungen"),
    ("gewichte", "Gewichte-Garantien"),
    ("anhaengelast", "Anhängelast"),
    ("reifen", "Reifen und Felgen (Motorfahrzeuge)"),
    ("bemerkungen", "Bemerkungen, beh. Auflagen"),
]
SECTION_BY_LABEL = {label: key for key, label in SECTION_ORDER}


#: Schadstoff-Spalten aus emissionen.txt, die auf der Detailseite auftauchen.
#: ET = Ersttreibstoff; die Werte stehen so im amtlichen Datensatz.
POLLUTANT_COLUMNS = (
    "ET-CO", "ET-THC", "ET-NMHC", "ET-NOx", "ET-THC+NOx", "ET-PM", "ET-PA",
    "ScCo2", "ScNo2", "ScNh3", "ScConsumption",
)


def _extras_to_rows(rows) -> tuple[list[ConsumptionRow], list[EmissionRow]]:
    """Zeilen aus type_approval_extras in die beiden Listen aufteilen."""
    consumption: list[ConsumptionRow] = []
    emissions: list[EmissionRow] = []
    for row in rows:
        if row["kind"] == "consumption":
            consumption.append(
                ConsumptionRow(
                    fuel_type=row["fuel_type"],
                    transmission=row["transmission"],
                    efficiency_category=row["efficiency_category"],
                    consumption_l100=_as_float(row["consumption_l100"]),
                    co2_g_km=row["co2_g_km"],
                    consumption_wltp_l100=_as_float(row["consumption_wltp_l100"]),
                    co2_wltp_g_km=row["co2_wltp_g_km"],
                    electric_kwh100=_as_float(row["electric_kwh100"]),
                    electric_range_km=row["electric_range_km"],
                )
            )
        else:
            data = row["data"] or {}
            if isinstance(data, str):
                data = json.loads(data)
            emissions.append(
                EmissionRow(
                    fuel_type=row["fuel_type"],
                    transmission=row["transmission"],
                    emission_code=row["emission_code"],
                    exhaust_code=row["exhaust_code"],
                    cylinders=row["cylinders"],
                    displacement_ccm=row["displacement_ccm"],
                    power_kw=_as_float(row["power_kw"]),
                    pollutants={
                        key: data[key]
                        for key in POLLUTANT_COLUMNS
                        if data.get(key) and data[key] not in ("0", "0.0")
                    },
                )
            )
    return consumption, emissions


def _as_float(value) -> float | None:
    return float(value) if value is not None else None


#: Ausliefer-Adresse eines Commons-Bildes. Special:FilePath ist die dafuer
#: vorgesehene, stabile Route und skaliert das Bild serverseitig.
def _commons_url(file_name: str, width: int) -> str:
    from urllib.parse import quote

    return (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        f"{quote(file_name)}?width={width}"
    )


def model_family(model: str | None) -> str:
    return (model or "").strip().split(" ")[0]


#: Plattformcode aus dem Variantenfeld. Er identifiziert die Generation.
#: Die Abtrennung ist je Hersteller anders - Semikolon, Doppelpunkt oder
#: schlicht zwei Leerzeichen. Siehe Migration 012.
PLATFORM_RE = re.compile(r"^\s*([A-Z0-9][A-Z0-9-]{0,7})\s*(?:[;:]|\s\s|$)")


def platform_code(variant: str | None) -> str:
    match = PLATFORM_RE.match((variant or "").strip())
    return match.group(1) if match else ""


#: Obergrenzen aus dem Typenschein. Das ASTRA fuehrt Abmessungen, Gewichte
#: und Sitzplaetze als Spanne ("40 Laenge von" / "40 Laenge bis"), weil eine
#: Typengenehmigung mehrere Karosserie- und Ausstattungsvarianten abdeckt.
#: Bisher zeigten wir nur den unteren Wert - das las sich wie eine exakte
#: Angabe, obwohl der Wagen laenger sein kann.
RANGE_UPPER = {
    "length_mm": ("Ausrüstung-Abmessungen", "40 Länge bis"),
    "width_mm": ("Ausrüstung-Abmessungen", "41 Breite bis"),
    "height_mm": ("Ausrüstung-Abmessungen", "42 Höhe bis"),
    "wheelbase_mm": ("Ausrüstung-Abmessungen", "44 Abstand Achse 1-2 bis"),
    "seats_total": ("Ausrüstung-Abmessungen", "37 Anzahl Plätze Total bis"),
    "weight_kg": ("Gewichte-Garantien", "52 Leergewicht bis"),
    "max_weight_kg": ("Gewichte-Garantien", "53 Garantiegewicht bis"),
}


def _upper_bounds(specs: dict, detail: VehicleDetail) -> dict[str, int]:
    """Obergrenzen einsammeln, soweit sie ueber dem Basiswert liegen.

    Das ASTRA traegt 0 ein, wo es keine Obergrenze gibt. Ein Wert, der dem
    unteren gleicht oder darunter liegt, ist keine Spanne und entfaellt.
    """
    out: dict[str, int] = {}
    for field, (section, key) in RANGE_UPPER.items():
        raw = (specs.get(section) or {}).get(key)
        try:
            upper = int(str(raw).strip().lstrip("'"))
        except (TypeError, ValueError):
            continue
        lower = getattr(detail, field, None)
        if lower is not None and upper > lower:
            out[field] = upper
    return out


def _matching_pattern(patterns: list[str], vin: str) -> str:
    """Das VIN-Muster der Genehmigung, auf das diese VIN passt."""
    for pattern in patterns:
        stem = pattern[:17]
        if re.fullmatch(stem.replace(".", "[A-HJ-NPR-Z0-9]"), vin[: len(stem)]):
            return stem
    return patterns[0][:17] if patterns else ""


def _apply_variant(detail: VehicleDetail, row, vin: str) -> None:
    """Werte der Zuordnungstabelle uebernehmen, wenn die VIN sie festlegt."""
    specs = row["specs"] or {}
    if isinstance(specs, str):
        specs = json.loads(specs)
    remarks = specs.get("Bemerkungen, beh. Auflagen") or {}
    pattern = _matching_pattern(detail.vin_patterns, vin.strip().upper())
    resolved = resolve_variant(vin.strip().upper(), pattern, remarks)
    if not resolved:
        return

    detail.variant_code = str(resolved.pop("variant_code", "")) or None
    own_ranges = resolved.pop("ranges", {}) or {}
    for field, value in resolved.items():
        setattr(detail, field, value)
        # Die Spanne ueber alle Ausfuehrungen ist jetzt hinfaellig. Hat die
        # gewaehlte Ausfuehrung selbst eine, tritt sie an ihre Stelle.
        detail.ranges.pop(field, None)
        if field in own_ranges:
            detail.ranges[field] = own_ranges[field]


def _to_detail(row) -> VehicleDetail:
    specs = row["specs"] or {}
    if isinstance(specs, str):
        specs = json.loads(specs)

    sections: list[SpecSection] = []
    for key, label in SECTION_ORDER:
        entries = specs.get(label)
        if entries:
            sections.append(SpecSection(key=key, label=label, entries=entries))
    # alles, was das ASTRA nicht einsortiert hat, haengt hinten an
    for label, entries in specs.items():
        if label not in SECTION_BY_LABEL and entries:
            sections.append(SpecSection(key="sonstiges", label=label, entries=entries))

    power_kw = float(row["power_kw"]) if row["power_kw"] is not None else None
    detail = VehicleDetail(
        id=row["id"],
        approval_number=row["approval_number"],
        approval_date=row["approval_date"].isoformat() if row["approval_date"] else None,
        eu_approval_number=row["eu_approval_number"],
        vin_patterns=list(row["vin_patterns"] or []),
        make=normalize_make(row["make"]),
        model=row["model"],
        variant=row["variant"],
        manufacturer=row["manufacturer"],
        vehicle_kind=row["vehicle_kind"],
        vehicle_class=row["vehicle_class"],
        body_form=row["body_form"],
        engine_make=row["engine_make"],
        engine_model=row["engine_model"],
        engine_code=row["engine_code"],
        fuel_type=row["fuel_type"],
        displacement_ccm=row["displacement_ccm"],
        power_kw=power_kw,
        power_ps=round(power_kw * 1.35962) if power_kw else None,
        power_rpm=row["power_rpm"],
        torque_nm=row["torque_nm"],
        torque_rpm=row["torque_rpm"],
        drive_type=row["drive_type"],
        transmission=row["transmission"],
        gears=row["gears"],
        doors=row["doors"],
        seats_total=row["seats_total"],
        top_speed_kmh=row["top_speed_kmh"],
        length_mm=row["length_mm"],
        width_mm=row["width_mm"],
        height_mm=row["height_mm"],
        wheelbase_mm=row["wheelbase_mm"],
        weight_kg=row["weight_kg"],
        max_weight_kg=row["max_weight_kg"],
        sections=sections,
        source=row["source_name"],
        attribution=row["attribution"],
    )
    detail.ranges = _upper_bounds(specs, detail)
    return detail


@router.get(
    "/vehicles/{vin}",
    response_model=list[VehicleMatch],
    summary="Passende Typengenehmigungen zu einer VIN",
)
async def vehicles_for_vin(
    request: Request,
    vin: str = Path(min_length=10, max_length=17, description="VIN oder VIN-Praefix ab 10 Zeichen"),
    limit: int = Query(60, ge=1, le=200),
) -> list[VehicleMatch]:
    """Trefferliste wie in der Oberflaeche.

    Es genuegt ein Praefix ab 10 Zeichen (WMI + Fahrzeugbeschreibung +
    Modelljahr) - die Seriennummer wird fuer die Zuordnung nicht gebraucht
    und soll auch gar nicht uebertragen werden.
    """
    app = request.app
    provider = app.state.type_approval_provider
    if provider is None:
        raise HTTPException(status_code=503, detail="type approval data unavailable")

    padded = vin.strip().upper().ljust(17, "0")
    structural = decode_structural(padded)
    result = await provider.fetch(structural)
    return [VehicleMatch(**m) for m in result.matches[:limit]]


#: Anzeigename einer Marke. Das ASTRA schreibt alles gross und kuerzt ab;
#: in einer Uebersicht liest sich das schlecht.
BRAND_NAMES = {
    "VW": "VW",
    "BMW": "BMW",
    "SEAT": "SEAT",
    "MAN": "MAN",
    "DS": "DS",
    "MG": "MG",
    "KTM": "KTM",
    "OPEL/VAUXHALL": "Opel / Vauxhall",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "MERCEDES-AMG": "Mercedes-AMG",
    "ALFA ROMEO": "Alfa Romeo",
    "LAND ROVER": "Land Rover",
    "ROLLS ROYCE": "Rolls-Royce",
}


def brand_name(make: str) -> str:
    """Markenname in lesbarer Schreibweise."""
    cleaned = " ".join((make or "").strip().split())
    if cleaned.upper() in BRAND_NAMES:
        return BRAND_NAMES[cleaned.upper()]
    if cleaned.isupper():
        return " ".join(
            "-".join(bit.capitalize() for bit in part.split("-"))
            for part in cleaned.split()
        )
    return cleaned


def slugify(value: str) -> str:
    """Adressteil aus einem Namen - eindeutig genug fuer den Rueckweg."""
    text = (value or "").strip().lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = text.replace("ß", "ss").replace("/", "-")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _data_uri(data) -> str | None:
    """Kleines Bild als eingebettete Adresse.

    Spart je Kachel eine Anfrage - bei 90 Marken der Unterschied zwischen
    "sofort da" und "baut sich sichtbar auf".
    """
    if not data:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(bytes(data)).decode("ascii")


def _thumb_url(row) -> str | None:
    """Vorschaubild einer Zeile - eigene Ablage bevorzugt."""
    if row["image_id"]:
        return f"/api/v1/image/{row['image_id']}?size=thumb"
    if row["image_file"]:
        return _commons_url(row["image_file"], 480)
    return None


@router.get(
    "/brands",
    response_model=list[BrandSummary],
    summary="Alle Marken des Fahrzeugkatalogs",
)
async def brands(request: Request) -> list[BrandSummary]:
    rows = await request.app.state.db.fetch(BRANDS_QUERY)
    return [
        BrandSummary(
            make=row["name"],
            name=row["name"],
            slug=row["slug"],
            vehicles=row["vehicles"],
            models=row["models"],
            logo_url=_data_uri(row["logo_thumb"]),
        )
        for row in rows
    ]


async def _brand_row(db, brand_slug: str):
    row = await db.fetchrow(
        "SELECT slug, name FROM catalog_brands WHERE slug = $1", brand_slug
    )
    if row is None:
        raise HTTPException(status_code=404, detail="brand not found")
    return row


@router.get(
    "/brands/{brand}",
    response_model=list[ModelSummary],
    summary="Modelle einer Marke",
)
async def brand_models(request: Request, brand: str) -> list[ModelSummary]:
    db = request.app.state.db
    await _brand_row(db, brand)
    models = await db.fetch(BRAND_MODELS_QUERY, brand)
    return [
        ModelSummary(
            model=m["name"],
            slug=m["slug"],
            generations=m["generations"],
            vehicles=m["vehicles"],
            year_from=m["year_from"],
            year_to=m["year_to"],
            thumb_url=(
                f"/api/v1/catalog-image/{brand}/{m['slug']}?size=thumb"
                if m["thumb"]
                else None
            ),
        )
        for m in models
    ]


@router.get(
    "/brands/{brand}/{model}",
    response_model=list[GenerationSummary],
    summary="Baureihen eines Modells",
)
async def model_generations(
    request: Request, brand: str, model: str
) -> list[GenerationSummary]:
    db = request.app.state.db
    await _brand_row(db, brand)
    rows = await db.fetch(MODEL_GENERATIONS_QUERY, brand, model)
    if not rows:
        raise HTTPException(status_code=404, detail="model not found")
    return [
        GenerationSummary(
            platform=row["name"],
            slug=row["slug"],
            year_from=row["year_from"],
            year_to=row["year_to"],
            vehicles=row["vehicles"],
            image_url=(
                f"/api/v1/catalog-image/{brand}/{model}/{row['slug']}"
                if row["thumb"]
                else None
            ),
            thumb_url=(
                f"/api/v1/catalog-image/{brand}/{model}/{row['slug']}?size=thumb"
                if row["thumb"]
                else None
            ),
        )
        for row in rows
    ]


@router.get(
    "/brands/{brand}/{model}/{generation}",
    response_model=list[GenerationVehicle],
    summary="Fahrzeuge einer Baureihe",
)
async def generation_vehicles(
    request: Request, brand: str, model: str, generation: str
) -> list[GenerationVehicle]:
    vehicles = await request.app.state.db.fetch(
        GENERATION_VEHICLES_QUERY, brand, model, generation
    )
    return [
        GenerationVehicle(
            id=v["id"],
            model=v["model"],
            fuel_type=v["fuel_type"],
            power_kw=float(v["power_kw"]) if v["power_kw"] is not None else None,
            power_ps=round(float(v["power_kw"]) * 1.35962) if v["power_kw"] else None,
            displacement_ccm=v["displacement_ccm"],
            transmission=v["transmission"],
            gears=v["gears"],
            drive_type=v["drive_type"],
            body_form=v["body_form"],
            doors=v["doors"],
            year_from=v["year_from"],
            year_to=v["year_to"],
            approvals=v["approvals"],
            approval_numbers=list(v["approval_numbers"] or []),
        )
        for v in vehicles
    ]


@router.get(
    "/catalog-gallery/{brand}/{model}/{generation}/{position}",
    summary="Bild der Baureihengalerie",
    response_class=Response,
)
async def catalog_gallery_image(
    request: Request, brand: str, model: str, generation: str, position: int,
    size: str = "full",
) -> Response:
    row = await request.app.state.db.fetchrow(
        CATALOG_GALLERY_IMAGE, brand, model, generation, position
    )
    return _image_response(row, size)


@router.get(
    "/catalog-image/{brand}/{model}",
    summary="Modellbild des Katalogs",
    response_class=Response,
)
async def catalog_model_image(
    request: Request, brand: str, model: str, size: str = "full"
) -> Response:
    row = await request.app.state.db.fetchrow(CATALOG_MODEL_IMAGE, brand, model)
    return _image_response(row, size)


@router.get(
    "/catalog-image/{brand}/{model}/{generation}",
    summary="Baureihenbild des Katalogs",
    response_class=Response,
)
async def catalog_generation_image(
    request: Request, brand: str, model: str, generation: str, size: str = "full"
) -> Response:
    row = await request.app.state.db.fetchrow(
        CATALOG_GENERATION_IMAGE, brand, model, generation
    )
    return _image_response(row, size)


def _image_response(row, size: str) -> Response:
    """Bilddaten ausliefern - sie aendern sich nach dem Import nicht mehr."""
    data = row and (row["thumb"] if size == "thumb" else row["image"])
    if not data:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(
        content=bytes(data),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


@router.get(
    "/brand-logo/{brand}",
    summary="Abgelegtes Markenlogo ausliefern",
    response_class=Response,
)
async def brand_logo(request: Request, brand: str, size: str = "full") -> Response:
    """Das Logo einer Marke aus der eigenen Ablage.

    In der Uebersicht steckt die kleine Fassung eingebettet in der Seite;
    dieser Weg ist fuer die Stellen, an denen ein einzelnes Logo genuegt.
    """
    row = await request.app.state.db.fetchrow(
        "SELECT logo AS image, logo_thumb AS thumb FROM catalog_brands"
        " WHERE slug = $1",
        brand,
    )
    return _image_response(row, size)


@router.get(
    "/image/{image_id}",
    summary="Abgelegtes Fahrzeugbild ausliefern",
    response_class=Response,
)
async def vehicle_image(
    request: Request, image_id: int, size: str = "full"
) -> Response:
    """Ein Bild aus der eigenen Datenbank.

    Die Dateien aendern sich nach dem Import nicht mehr, deshalb darf der
    Browser sie lange behalten.
    """
    row = await request.app.state.db.fetchrow(STORED_IMAGE_QUERY, image_id)
    data = row and (row["thumb"] if size == "thumb" else row["image"])
    if not data:
        raise HTTPException(status_code=404, detail="image not found")
    return Response(
        content=bytes(data),
        media_type=row["content_type"] or "image/jpeg",
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


@router.get(
    "/vehicle/{vehicle_id}",
    response_model=VehicleDetail,
    summary="Vollstaendige technische Daten einer Typengenehmigung",
)
async def vehicle_detail(
    request: Request, vehicle_id: int, vin: str = ""
) -> VehicleDetail:
    db = request.app.state.db
    row = await db.fetchrow(TYPE_APPROVAL_DETAIL_QUERY, vehicle_id)
    if row is None:
        raise HTTPException(status_code=404, detail="vehicle not found")

    detail = _to_detail(row)
    # Mit der VIN laesst sich oft die konkrete Ausfuehrung bestimmen und
    # damit aus "3106-3216 mm" ein Wert werden. Siehe decoder/variant.py.
    if vin:
        _apply_variant(detail, row, vin)
    if row["approval_number"]:
        extras = await db.fetch(TYPE_APPROVAL_EXTRAS_QUERY, row["approval_number"])
        detail.consumption, detail.emissions = _extras_to_rows(extras)

    if row["make"]:
        logo = await db.fetchrow(BRAND_LOGO_QUERY, row["make"])
        if logo:
            detail.logo = BrandLogo(
                # SVG-Logos werden von Commons als PNG in der gewuenschten
                # Breite ausgeliefert - das rendert ueberall zuverlaessig.
                url=(
                    f"/api/v1/brand-logo/{slugify(row['make'])}"
                    if logo["stored"]
                    else _commons_url(logo["file_name"], 160)
                ),
                page_url=logo["page_url"],
                license=logo["license"],
                license_url=logo["license_url"],
                author=logo["author"],
            )

    # Zuerst das Bild der Katalog-Baureihe: es zeigt genau diese
    # Generation, waehrend die Aufnahmen aus Commons nur ueber Marke und
    # Modellname gefunden wurden.
    galerie = await db.fetch(CATALOG_GALLERY_FOR_APPROVAL, vehicle_id)
    for bild in galerie:
        pfad = (
            f"/api/v1/catalog-gallery/{bild['brand_slug']}/{bild['model_slug']}"
            f"/{bild['generation_slug']}/{bild['position']}"
        )
        detail.images.append(
            VehicleImage(
                file_key=f"katalog-{bild['generation_slug']}-{bild['position']}",
                url=pfad,
                thumb_url=f"{pfad}?size=thumb",
                page_url=bild["source_url"],
                license="ADAC Autokatalog",
            )
        )

    katalog = await db.fetchrow(CATALOG_IMAGE_FOR_APPROVAL, vehicle_id)
    if not galerie and katalog and katalog["has_image"]:
        pfad = (
            f"/api/v1/catalog-image/{katalog['brand_slug']}"
            f"/{katalog['model_slug']}/{katalog['generation_slug']}"
        )
        detail.images.append(
            VehicleImage(
                file_key=f"katalog-{katalog['generation_slug']}",
                url=pfad,
                thumb_url=f"{pfad}?size=thumb",
                license="ADAC Autokatalog",
            )
        )

    family = model_family(row["model"])
    # Aufnahmen aus Commons nur, wenn der Katalog keine Galerie hat.
    if not detail.images and row["make"] and family:
        platform = platform_code(row["variant"])
        images = await db.fetch(
            VEHICLE_IMAGES_QUERY, row["make"], family, row["model_year_from"], platform
        )
        detail.images += [
            VehicleImage(
                file_key=i["file_name"],
                # Eigene Ablage bevorzugt: kein fremder Abruf im Ladepfad.
                url=(f"/api/v1/image/{i['id']}" if i["stored"]
                     else _commons_url(i["file_name"], 1200)),
                thumb_url=(f"/api/v1/image/{i['id']}?size=thumb" if i["stored"]
                           else _commons_url(i["file_name"], 480)),
                page_url=i["page_url"],
                license=i["license"],
                license_url=i["license_url"],
                author=i["author"],
                description=i["description"],
                width=i["width"],
                height=i["height"],
            )
            for i in images
        ]
    return detail


# ---------------------------------------------------------------------------
# Startseite: aktuelle Suchen und Referenztabellen
# ---------------------------------------------------------------------------


@router.get("/recent", summary="Zuletzt gesuchte Fahrzeuge")
async def recent_lookups(
    request: Request, limit: int = Query(10, ge=1, le=50)
) -> list[dict]:
    """Fuer die Startseite.

    Ausgegeben wird nur, was ohnehin protokolliert wird: die maskierte VIN
    (Position 1-11) sowie Marke, Modell und Baujahr. Kein Nutzerbezug,
    keine Seriennummer.
    """
    rows = await request.app.state.db.fetch(RECENT_LOOKUPS_QUERY, limit)
    return [
        {
            "vin_masked": r["vin_masked"],
            "make": r["make"],
            "model": r["model"],
            "model_year": r["model_year"],
            "requested_at": r["requested_at"].isoformat(),
        }
        for r in rows
    ]


@router.get("/reference/model-years", summary="Modelljahr-Codes (Position 10)")
async def reference_model_years() -> list[dict]:
    """Die Tabelle stammt aus derselben Konstante wie der Decoder.

    Damit kann die erklaerende Tabelle auf der Startseite gar nicht von dem
    abweichen, was die Decodierung tatsaechlich tut.
    """
    return [
        {"code": code, "years": list(years)}
        for code, years in MODEL_YEAR_CODES.items()
    ]


@router.get("/reference/countries", summary="Laenderbereiche der WMI (ISO 3780)")
async def reference_countries() -> list[dict]:
    regions = {code: name for _, _, code, name in REGIONS}
    out = []
    for start, end, country, iso in COUNTRY_RANGES:
        region_code, _ = lookup_region(start[0])
        out.append(
            {
                "range": f"{start}-{end}",
                "country": country,
                "country_code": iso,
                "region_code": region_code,
                "region": regions.get(region_code or "", ""),
            }
        )
    return out
