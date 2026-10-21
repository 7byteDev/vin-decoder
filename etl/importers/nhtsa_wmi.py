"""Importer: WMI-Stammdaten aus der NHTSA-vPIC-API.

vPIC ist ein Werk der US-Bundesregierung und damit gemeinfrei. Der Datensatz
enthaelt auch sehr viele europaeische Hersteller inklusive Laenderangabe -
er ist deshalb die tragfaehigste freie Basis fuer die Tabelle ``wmi``.

Ablauf:
    1. ``GetAllManufacturers`` seitenweise -> Hersteller-IDs
    2. ``GetWMIsForManufacturer/{id}``     -> WMIs je Hersteller
    3. Upsert in ``manufacturers`` und ``wmi``

Alle Antworten werden unter etl/data/raw/nhtsa_wmi/ zwischengespeichert,
Wiederholungslaeufe kosten daher kaum Zeit.
"""

from __future__ import annotations

import asyncio
import json
import logging

import asyncpg

from ..common import (
    CachedClient,
    RateLimited,
    chunked,
    finish_source,
    normalize_country,
    source_id,
)

logger = logging.getLogger("etl.nhtsa_wmi")

SOURCE_KEY = "nhtsa_vpic"
BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

MANUFACTURER_UPSERT = """
INSERT INTO manufacturers (name, normalized_name, common_name, country, country_code)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (normalized_name) DO UPDATE SET
    common_name  = COALESCE(EXCLUDED.common_name, manufacturers.common_name),
    country      = COALESCE(EXCLUDED.country, manufacturers.country),
    country_code = COALESCE(EXCLUDED.country_code, manufacturers.country_code)
"""

WMI_UPSERT = """
INSERT INTO wmi (code, manufacturer_id, manufacturer_name, common_name, country,
                 country_code, region, vehicle_type, source_id, confidence, raw)
SELECT $1, m.id, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb
FROM (SELECT id FROM manufacturers WHERE normalized_name = $11) m
ON CONFLICT (code, source_id, manufacturer_name, COALESCE(vehicle_type, ''))
DO UPDATE SET
    common_name  = COALESCE(EXCLUDED.common_name, wmi.common_name),
    country      = COALESCE(EXCLUDED.country, wmi.country),
    country_code = COALESCE(EXCLUDED.country_code, wmi.country_code),
    region       = COALESCE(EXCLUDED.region, wmi.region),
    confidence   = EXCLUDED.confidence,
    raw          = EXCLUDED.raw
"""


def normalize_name(name: str) -> str:
    return " ".join(name.strip().upper().split())


async def fetch_manufacturers(client: CachedClient, max_pages: int | None) -> list[dict]:
    """Alle Hersteller seitenweise laden (100 pro Seite)."""
    manufacturers: dict[int, dict] = {}
    page = 1
    while True:
        if max_pages is not None and page > max_pages:
            break
        payload = await client.get_json(
            f"{BASE_URL}/GetAllManufacturers",
            cache_key=f"manufacturers_p{page:04d}",
            params={"format": "json", "page": str(page)},
        )
        results = (payload or {}).get("Results") or []
        if not results:
            break
        for row in results:
            mfr_id = row.get("Mfr_ID")
            if mfr_id:
                manufacturers[int(mfr_id)] = row
        logger.info(
            "Hersteller-Seite %s: %s Eintraege (gesamt %s)",
            page, len(results), len(manufacturers),
        )
        page += 1
    return list(manufacturers.values())


def filter_focus(manufacturers: list[dict]) -> list[dict]:
    """Auf Europa/Tuerkei einschraenken, BEVOR pro Hersteller abgefragt wird.

    Das ist der entscheidende Punkt fuer die Laufzeit: vPIC fuehrt rund
    23.000 Hersteller, davon liegen nur etwa 680 in Europa oder der
    Tuerkei - der grosse Rest sind US-Anhaenger- und Aufbauhersteller.
    Ohne diesen Filter kostet ein Lauf 23.000 Anfragen statt 680.
    """
    kept = []
    for mfr in manufacturers:
        _, _, region = normalize_country(mfr.get("Country"))
        if region in ("EU", "TR"):
            kept.append(mfr)
    return kept


async def fetch_wmis(client: CachedClient, manufacturers: list[dict]) -> list[dict]:
    """WMIs je Hersteller abrufen (getaktet, siehe CachedClient)."""
    async def one(mfr: dict) -> list[dict]:
        mfr_id = mfr["Mfr_ID"]
        payload = await client.get_json(
            f"{BASE_URL}/GetWMIsForManufacturer/{mfr_id}",
            cache_key=f"wmi_mfr_{mfr_id}",
            params={"format": "json"},
        )
        results = (payload or {}).get("Results") or []
        for row in results:
            row.setdefault("_CommonName", mfr.get("Mfr_CommonName"))
        return results

    collected: list[dict] = []
    total = len(manufacturers)
    done = 0
    for batch in chunked(manufacturers, 50):
        chunks = await asyncio.gather(*(one(m) for m in batch))
        for rows in chunks:
            collected.extend(rows)
        done += len(batch)
        logger.info(
            "WMI-Abruf: %s/%s Hersteller, %s WMI-Zeilen", min(done, total), total, len(collected)
        )
    return collected


async def run(
    conn: asyncpg.Connection,
    *,
    max_pages: int | None = None,
    concurrency: int = 2,
    use_cache: bool = True,
    focus_only: bool = False,
    rate: float = 1.0,
) -> int:
    """Import ausfuehren.

    ``focus_only`` schraenkt auf Europa/Tuerkei ein - und zwar bereits auf
    der Herstellerliste, nicht erst beim Schreiben. ``rate`` ist der
    Mindestabstand zwischen zwei Anfragen in Sekunden.
    """
    sid = await source_id(conn, SOURCE_KEY)

    async with CachedClient(
        cache_name="nhtsa_wmi",
        concurrency=concurrency,
        use_cache=use_cache,
        min_interval=rate,
    ) as client:
        manufacturers = await fetch_manufacturers(client, max_pages)
        logger.info("%s Hersteller in vPIC.", len(manufacturers))
        if focus_only:
            manufacturers = filter_focus(manufacturers)
            logger.info("Nach Filter Europa/Tuerkei: %s Hersteller.", len(manufacturers))
        try:
            wmi_rows = await fetch_wmis(client, manufacturers)
        except RateLimited as exc:
            logger.error("%s", exc)
            raise SystemExit(2) from exc

    logger.info("%s WMI-Zeilen abgerufen, wird geschrieben ...", len(wmi_rows))

    mfr_batch: dict[str, tuple] = {}
    wmi_batch: list[tuple] = []
    skipped = 0

    for row in wmi_rows:
        code = (row.get("WMI") or "").strip().upper()
        name = (row.get("Name") or "").strip()
        if not code or not name or len(code) not in (3, 6):
            skipped += 1
            continue

        country, iso, region = normalize_country(row.get("Country"))
        normalized = normalize_name(name)
        common = row.get("_CommonName") or None
        mfr_batch[normalized] = (name, normalized, common, country, iso)

        # 6-stellige WMIs sind Kleinserien-Kennungen und damit spezifischer
        confidence = 0.90 if len(code) == 6 else 0.85
        wmi_batch.append(
            (
                code, name, common, country, iso, region,
                (row.get("VehicleType") or "").strip() or None,
                sid, confidence,
                json.dumps({k: v for k, v in row.items() if not k.startswith("_")}),
                normalized,
            )
        )

    async with conn.transaction():
        await conn.executemany(MANUFACTURER_UPSERT, list(mfr_batch.values()))
        for batch in chunked(wmi_batch, 1000):
            await conn.executemany(WMI_UPSERT, batch)

    count = await conn.fetchval("SELECT count(*) FROM wmi WHERE source_id = $1", sid)
    await finish_source(conn, SOURCE_KEY, count)
    logger.info(
        "Fertig: %s Hersteller, %s WMI-Zeilen geschrieben (%s uebersprungen). Bestand: %s",
        len(mfr_batch), len(wmi_batch), skipped, count,
    )
    return count
