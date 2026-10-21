"""Importer: herstellerspezifische VDS-Regeln aus ``idlesign/vininfo``.

Lizenz der Quelle: BSD-3-Clause (Namensnennung erforderlich, siehe
``sources.attribution``). Das Paket wird als Abhaengigkeit installiert und
zur Laufzeit ausgelesen - so bleibt der Import bei einem Update der
Bibliothek einfach wiederholbar.

vininfo beschreibt Regeln als ``Detail(('vds', index), {code: name})``.
Uebersetzt wird das in Zeilen der Tabelle ``manufacturer_patterns``:

    ('vds', 0) -> VIN-Position 4          (VDS beginnt bei Position 4)
    ('vis', 1) -> VIN-Position 11         (VIS beginnt bei Position 10)

Regeln, die von einem zweiten Zeichen abhaengen (z. B. der Motorcode bei
Opel haengt am Modellcode), werden zu Mehrpositions-Mustern expandiert.
Die Seriennummer wird bewusst NICHT importiert - sie identifiziert ein
einzelnes Fahrzeug.
"""

from __future__ import annotations

import inspect
import json
import logging
from types import SimpleNamespace
from typing import Any

import asyncpg

from ..common import chunked, finish_source, source_id

logger = logging.getLogger("etl.vininfo")

SOURCE_KEY = "vininfo"

#: VIN-Startposition (1-basiert) je vininfo-Abschnitt
SECTION_OFFSET = {"vin": 1, "wmi": 1, "vds": 4, "vis": 10}

#: vininfo-Detailname -> Attribut im eigenen Schema
ATTRIBUTE_MAP = {
    "model": "model",
    "body": "body_class",
    "engine": "engine_model",
    "plant": "plant_city",
    "transmission": "transmission",
    # "serial" wird bewusst ausgelassen (Einzelfahrzeugbezug)
}

WMI_UPSERT = """
INSERT INTO wmi (code, manufacturer_name, common_name, source_id, confidence, raw)
VALUES ($1, $2, $3, $4, $5, $6::jsonb)
ON CONFLICT (code, source_id, manufacturer_name, COALESCE(vehicle_type, ''))
DO UPDATE SET common_name = EXCLUDED.common_name,
              confidence  = EXCLUDED.confidence,
              raw         = EXCLUDED.raw
"""

PATTERN_UPSERT = """
INSERT INTO manufacturer_patterns
    (wmi_code, attribute, positions, match_type, pattern, value, confidence, source_id, raw)
VALUES ($1, $2, $3::smallint[], 'exact', $4, $5, $6, $7, $8::jsonb)
ON CONFLICT (wmi_code, attribute, positions, pattern, value, source_id, COALESCE(year_from, 0))
DO UPDATE SET confidence = EXCLUDED.confidence, raw = EXCLUDED.raw
"""


def _positions(section: str, index: Any) -> list[int] | None:
    offset = SECTION_OFFSET.get(section)
    if offset is None:
        return None
    if isinstance(index, int):
        return [offset + index]
    if isinstance(index, slice):
        if index.stop is None:  # offenes Ende = Seriennummer -> nicht importieren
            return None
        return list(range(offset + (index.start or 0), offset + index.stop))
    return None


def _expand_callable(defs: Any, model_defs: dict) -> dict[str, dict]:
    """Modellabhaengige Definitionen aufloesen.

    vininfo uebergibt der Funktion das Details-Objekt; genutzt wird daraus in
    der Praxis ``details.model.code``. Wir rufen sie deshalb je Modellcode mit
    einem Stub auf und erhalten so ein Muster ueber zwei Positionen.
    """
    expanded: dict[str, dict] = {}
    for model_code in model_defs:
        stub = SimpleNamespace(model=SimpleNamespace(code=model_code, name=None))
        try:
            result = defs(stub)
        except Exception:  # pragma: no cover - defensiv, Bibliothek kann sich aendern
            continue
        if isinstance(result, dict) and result:
            expanded[model_code] = result
    return expanded


def collect() -> tuple[list[tuple], list[tuple]]:
    """(wmi_rows, pattern_rows) aus vininfo einsammeln - ohne DB-Zugriff."""
    try:
        from vininfo.details._base import Detail, VinDetails  # noqa: F401
        from vininfo.dicts.wmi import WMI
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "vininfo ist nicht installiert - 'pip install vininfo' (BSD-3-Clause)"
        ) from exc

    wmi_rows: list[tuple] = []
    brand_codes: dict[Any, list[str]] = {}

    for code, brand in WMI.items():
        code = code.strip().upper()
        if not 2 <= len(code) <= 6:
            continue
        if isinstance(brand, str):
            title = brand
            manufacturer = brand
            extra: dict[str, Any] = {}
        else:
            title = getattr(brand, "title", None) or str(brand)
            manufacturer = getattr(brand, "manufacturer", None) or title
            extra = {
                "year_position": getattr(brand, "year_position", None),
                "uses_sae_checkdigit": getattr(brand, "uses_sae_checkdigit", None),
            }
            brand_codes.setdefault(brand, []).append(code)
        wmi_rows.append(
            (code, manufacturer, title, json.dumps({"wmi": code, "brand": title, **extra}))
        )

    pattern_rows: list[tuple] = []
    for brand, codes in brand_codes.items():
        extractor = getattr(brand, "extractor", None)
        if extractor is None:
            continue
        pattern_rows.extend(_patterns_for(extractor, codes, getattr(brand, "title", "")))

    return wmi_rows, pattern_rows


def _patterns_for(extractor: type, codes: list[str], brand_title: str) -> list[tuple]:
    from vininfo.details._base import Detail

    details: dict[str, Any] = {}
    for klass in reversed(inspect.getmro(extractor)):
        for name, obj in vars(klass).items():
            if isinstance(obj, Detail):
                details[name] = obj

    model_detail = details.get("model")
    model_defs = (
        model_detail.defs
        if model_detail is not None and isinstance(model_detail.defs, dict)
        else {}
    )

    rows: list[tuple] = []
    for name, detail in details.items():
        attribute = ATTRIBUTE_MAP.get(name)
        if attribute is None or detail.source is None:
            continue
        positions = _positions(detail.source[0], detail.source[1])
        if not positions:
            continue

        if callable(detail.defs):
            model_positions = (
                _positions(*model_detail.source) if model_detail and model_detail.source else None
            )
            if not model_positions or len(model_positions) != 1:
                logger.debug("%s.%s: dynamische Regel nicht aufloesbar", brand_title, name)
                continue
            for model_code, mapping in _expand_callable(detail.defs, model_defs).items():
                for code, value in mapping.items():
                    rows.extend(
                        _rows(
                            codes,
                            attribute,
                            model_positions + positions,
                            model_code + code,
                            value,
                            brand_title,
                            confidence=0.75,
                        )
                    )
            continue

        for code, value in (detail.defs or {}).items():
            rows.extend(
                _rows(codes, attribute, positions, code, value, brand_title, confidence=0.80)
            )
    return rows


def _rows(
    wmi_codes: list[str],
    attribute: str,
    positions: list[int],
    pattern: str,
    value: Any,
    brand_title: str,
    *,
    confidence: float,
) -> list[tuple]:
    """Eine Regel auf alle WMIs der Marke verteilen; Listen = mehrdeutig."""
    values = value if isinstance(value, (list, tuple)) else [value]
    # mehrere moegliche Werte fuer denselben Code -> jeder einzeln schwaecher
    per_value = confidence if len(values) == 1 else round(confidence * 0.6, 2)
    out: list[tuple] = []
    for wmi_code in wmi_codes:
        for item in values:
            if not item:
                continue
            out.append(
                (
                    wmi_code,
                    attribute,
                    positions,
                    pattern,
                    str(item),
                    per_value,
                    json.dumps({"brand": brand_title, "ambiguous": len(values) > 1}),
                )
            )
    return out


async def run(conn: asyncpg.Connection, *, dry_run: bool = False) -> int:
    sid = await source_id(conn, SOURCE_KEY)
    wmi_rows, pattern_rows = collect()
    logger.info("vininfo: %s WMI-Zeilen, %s Regeln", len(wmi_rows), len(pattern_rows))
    if dry_run:
        return len(pattern_rows)

    async with conn.transaction():
        for batch in chunked(wmi_rows, 500):
            await conn.executemany(
                WMI_UPSERT, [(c, m, t, sid, 0.75, raw) for c, m, t, raw in batch]
            )
        for batch in chunked(pattern_rows, 500):
            await conn.executemany(
                PATTERN_UPSERT,
                [(w, a, p, pat, v, conf, sid, raw) for w, a, p, pat, v, conf, raw in batch],
            )

    count = await conn.fetchval(
        "SELECT count(*) FROM manufacturer_patterns WHERE source_id = $1", sid
    )
    await finish_source(conn, SOURCE_KEY, count)
    logger.info("vininfo fertig: %s Regeln in der Datenbank.", count)
    return count
