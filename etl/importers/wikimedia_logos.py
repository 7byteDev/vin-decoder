"""Importer: Markenlogos aus Wikimedia Commons.

Wikidata fuehrt zu jeder Marke ein Logo (Eigenschaft P154), das als Datei
auf Commons liegt. Das ist die kuratierte Fassung - deutlich verlaesslicher
als eine Volltextsuche, die auch Haendlerschilder und Fanart findet.

Zur Lizenz: Firmenlogos sind Marken- und teils Urheberrecht. Auf Commons
liegen sie meist als "PD-textlogo" (zu einfach fuer Urheberrechtsschutz)
oder gemeinfrei, immer mit dem Hinweis, dass Markenrechte bestehen
bleiben. Die Anzeige eines Logos zur Bezeichnung genau dieses Herstellers
ist eine beschreibende Nutzung - das Logo steht neben dem Fahrzeug, das
tatsaechlich von dieser Marke stammt, nicht als eigenes Kennzeichen. Die
Lizenzangabe wird trotzdem mitgefuehrt und angezeigt.
"""

from __future__ import annotations

import logging
import re

import asyncpg
import httpx

from ..common import CachedClient
from .image_store import fetch_and_prepare

logger = logging.getLogger("etl.logos")

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

#: Beschreibungen, die auf einen Fahrzeughersteller hindeuten.
CARMAKER = re.compile(
    r"car|automobile|automotive|vehicle|motor|manufactur|marque|brand", re.I
)
#: Beschreibungen, die gegen die gesuchte Marke sprechen (Vorgaenger,
#: Museen, Vereine, Modellreihen).
NOT_A_BRAND = re.compile(
    r"museum|club|association|racing team|album|film|village|surname|given name", re.I
)

#: TARGA kuerzt Marken ab; Wikidata kennt den vollen Namen.
MAKE_ALIASES = {
    "VW": "Volkswagen",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "ALFA ROMEO": "Alfa Romeo",
    "LAND ROVER": "Land Rover",
    "ROLLS ROYCE": "Rolls-Royce",
    "SKODA": "Škoda Auto",
    "CITROEN": "Citroën",
    "OPEL/VAUXHALL": "Opel",
    "MAN": "MAN Truck & Bus",
    "DS": "DS Automobiles",
    "MINI": "Mini (marque)",
    "HUERLIMANN": "Hürlimann",
    "NEW HOLLAND": "New Holland Agriculture",
    "CASE IH": "Case IH",
    "DEUTZ-FAHR": "Deutz-Fahr",
    "SSANGYONG": "SsangYong Motor",
    "MERCEDES-AMG": "Mercedes-AMG",
    "VW NUTZFAHRZEUGE": "Volkswagen Nutzfahrzeuge",
    # Umbauer tragen den Namen des Basisherstellers plus eigenen Zusatz;
    # ein eigenes Logo gibt es dafuer meist nicht.
    "CITROEN-DANGEL": "Dangel",
    "PEUGEOT-DANGEL": "Dangel",
    "FIAT-DANGEL": "Dangel",
    # Marken, deren Name allein zu Verwechslungen fuehrt oder bei Wikidata
    # anders lautet als im Typenschein.
    "MG": "MG Motor",
    "BYD": "BYD Auto",
    "DFM": "Dongfeng Motor Corporation",
    "DFSK": "DFSK Motor",
    "BAW": "Beijing Automobile Works",
    "SERES": "Seres Group",
    "MAXUS": "Maxus (marque)",
    "MICROCAR": "Microcar",
    "MICRO": "Micro Mobility Systems",
    "XEV": "XEV",
    "MOBILIZE": "Mobilize (brand)",
    "VOYAH": "Voyah",
    "ZEEKR": "Zeekr",
    "XPENG": "Xpeng",
    "LEAPMOTOR": "Leapmotor",
    "TESLA": "Tesla, Inc.",
    "ROVER": "Rover Company",
    "ALPINE": "Alpine (automobile manufacturer)",
    "AIXAM": "Aixam",
    "HANSA": "Hansa-Lloyd",
}

LOGO_UPSERT = """
INSERT INTO brand_logos (make, file_name, page_url, license, license_url,
                         author, width, height, wikidata_id,
                         image, content_type, bytes, stored_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::bytea, $11, $12,
        CASE WHEN $10::bytea IS NULL THEN NULL ELSE now() END)
ON CONFLICT (make) DO UPDATE SET
    file_name = EXCLUDED.file_name, page_url = EXCLUDED.page_url,
    license = EXCLUDED.license, license_url = EXCLUDED.license_url,
    author = EXCLUDED.author, width = EXCLUDED.width, height = EXCLUDED.height,
    wikidata_id = EXCLUDED.wikidata_id, imported_at = now(),
    image = coalesce(EXCLUDED.image, brand_logos.image),
    content_type = coalesce(EXCLUDED.content_type, brand_logos.content_type),
    bytes = coalesce(EXCLUDED.bytes, brand_logos.bytes),
    stored_at = CASE WHEN EXCLUDED.image IS NULL THEN brand_logos.stored_at
                     ELSE now() END
"""

#: Ausliefer-Adresse einer Commons-Datei in gewuenschter Breite.
COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width={width}"

LOOKUP_UPSERT = """
INSERT INTO brand_logo_lookups (make, found, checked_at)
VALUES ($1, $2, now())
ON CONFLICT (make) DO UPDATE SET found = EXCLUDED.found, checked_at = now()
"""

#: Marken nach Anzahl der Genehmigungen, ungeprueft zuerst.
MAKES_QUERY = """
SELECT t.make, count(*) AS n
FROM type_approvals t
WHERE t.make IS NOT NULL AND t.make <> ''
  AND NOT EXISTS (SELECT 1 FROM brand_logos l WHERE l.make = t.make)
  -- $2: nur Marken, die auch im Fahrzeugkatalog stehen. Der Bestand
  -- fuehrt hunderte Kleinstmarken, deren Logo niemand sucht.
  AND ($2 IS NOT TRUE
       OR EXISTS (SELECT 1 FROM brand_catalog c WHERE c.make = t.make))
GROUP BY 1
ORDER BY n DESC
LIMIT $1
"""


def search_make(make: str) -> str:
    """Markenname, wie ihn Wikidata schreibt."""
    cleaned = " ".join((make or "").strip().split())
    alias = MAKE_ALIASES.get(cleaned.upper())
    if alias:
        return alias
    # Kurze Namen sind Abkuerzungen und bleiben gross: aus "MG" wurde sonst
    # "Mg" - und Wikidata liefert dazu das chemische Element Magnesium.
    if len(cleaned) <= 4 and cleaned.isupper():
        return cleaned
    if cleaned.isupper():
        return "-".join(part.capitalize() for part in cleaned.split("-"))
    return cleaned


def _clean_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", "", str(value)).strip()
    return re.sub(r"\s+", " ", text)[:200] or None


#: Jahreszahl im Dateinamen eines Logos ("Logo-citroen-1919.png").
LOGO_YEAR = re.compile(r"(1[89]\d\d|20\d\d)")


def _qualifier_year(qualifiers: dict, prop: str) -> int | None:
    """Jahreszahl eines Zeit-Qualifikators ("+2016-00-00T00:00:00Z" -> 2016)."""
    for entry in qualifiers.get(prop, []):
        value = entry.get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("time"):
            try:
                return int(value["time"][1:5])
            except ValueError:
                return None
    return None


def current_logo(claims: list[dict]) -> str | None:
    """Die aktuell gueltige Fassung aus mehreren P154-Angaben waehlen.

    Wikidata fuehrt zu vielen Marken mehrere Logos, unterschieden durch
    die Qualifikatoren "Beginn" (P580) und "Ende" (P582). Ohne Auswertung
    landet man beim erstbesten - bei Citroen war das die Fassung von 1919.
    Bevorzugt wird deshalb ein Logo ohne Enddatum, danach das mit dem
    juengsten Beginn.
    """
    scored: list[tuple[int, int, str]] = []
    for claim in claims:
        snak = claim.get("mainsnak", {})
        if not snak.get("datavalue"):
            continue
        name = snak["datavalue"]["value"]
        qualifiers = claim.get("qualifiers", {})

        ended = _qualifier_year(qualifiers, "P582")
        started = _qualifier_year(qualifiers, "P580")
        # Ohne Enddatum = noch gueltig; sonst nach Endjahr sortieren
        rank = 2 if ended is None else 1
        # Faellt beides weg, hilft die Jahreszahl im Dateinamen
        if started is None and ended is None:
            match = LOGO_YEAR.search(name)
            if match and int(match.group(1)) < 1990:
                rank = 0
        scored.append((rank, started or ended or 0, name))

    if not scored:
        return None
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return scored[0][2]


def pick_entity(candidates: list[dict], entities: dict, wanted: str) -> tuple[str, str] | None:
    """Das Objekt der gesuchten Marke mit Logo auswaehlen.

    Die Wikidata-Suche liefert zu "Skoda" auch "Laurin & Klement" - den
    historischen Vorgaenger. Deshalb wird bewertet: exakte Namensgleichheit
    zaehlt am meisten, danach eine Beschreibung, die nach Fahrzeugbau
    klingt.
    """
    best: tuple[int, str, str] | None = None
    for candidate in candidates:
        qid = candidate["id"]
        entity = entities.get(qid) or {}
        claims = entity.get("claims", {})
        logo = current_logo(claims.get("P154", []))
        if not logo:
            continue

        label = (entity.get("labels", {}).get("en", {}).get("value") or "").strip()
        description = entity.get("descriptions", {}).get("en", {}).get("value", "")
        if NOT_A_BRAND.search(description):
            continue

        score = 0
        if label.casefold() == wanted.casefold():
            score += 6
        elif wanted.casefold() in label.casefold():
            score += 3
        if CARMAKER.search(description):
            score += 3
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, qid, logo)

    return (best[1], best[2]) if best else None


async def logo_for(client: CachedClient, make: str) -> dict | None:
    """Logo einer Marke samt Lizenzangabe holen."""
    wanted = search_make(make)
    search = await client.get_json(
        WIKIDATA_API,
        cache_key=f"logo_search_{wanted}",
        params={
            "action": "wbsearchentities", "search": wanted, "language": "en",
            "type": "item", "limit": "8", "format": "json",
        },
    )
    candidates = (search or {}).get("search") or []
    if not candidates:
        return None

    entities_payload = await client.get_json(
        WIKIDATA_API,
        cache_key=f"logo_entities_{wanted}",
        params={
            "action": "wbgetentities", "ids": "|".join(c["id"] for c in candidates),
            "props": "claims|labels|descriptions", "languages": "en", "format": "json",
        },
    )
    entities = (entities_payload or {}).get("entities") or {}
    picked = pick_entity(candidates, entities, wanted)
    if not picked:
        return None
    qid, file_name = picked

    info = await client.get_json(
        COMMONS_API,
        cache_key=f"logo_info_{file_name}",
        params={
            "action": "query", "titles": f"File:{file_name}", "prop": "imageinfo",
            "iiprop": "url|extmetadata|size", "format": "json",
        },
    )
    pages = ((info or {}).get("query") or {}).get("pages") or {}
    page = next(iter(pages.values()), {})
    image = (page.get("imageinfo") or [{}])[0]
    meta = image.get("extmetadata") or {}

    return {
        "file_name": file_name,
        "page_url": image.get("descriptionurl"),
        "license": _clean_html((meta.get("LicenseShortName") or {}).get("value")),
        "license_url": (meta.get("LicenseUrl") or {}).get("value"),
        "author": _clean_html((meta.get("Artist") or {}).get("value")),
        "width": image.get("width"),
        "height": image.get("height"),
        "wikidata_id": qid,
    }


async def run(
    conn: asyncpg.Connection,
    *,
    limit: int = 120,
    rate: float = 3.5,
    use_cache: bool = True,
    catalog_only: bool = False,
) -> int:
    """Logos der haeufigsten Marken nachladen."""
    makes = await conn.fetch(MAKES_QUERY, limit, catalog_only)
    if not makes:
        logger.info("Keine offenen Marken - nichts zu tun.")
        return 0

    logger.info("%s Marken werden abgefragt (%.1f s Abstand).", len(makes), rate)
    found = 0

    async with CachedClient(
        cache_name="logos", concurrency=1, min_interval=rate, use_cache=use_cache
    ) as client, httpx.AsyncClient(
        headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
        follow_redirects=True,
    ) as downloader:
        for index, row in enumerate(makes, start=1):
            make = row["make"]
            try:
                logo = await logo_for(client, make)
            except Exception as exc:  # pragma: no cover - Netz/Format
                logger.warning("%s: %s", make, exc)
                logo = None

            if logo and logo["file_name"]:
                # Die Datei gleich mitnehmen: sonst laedt jede Marken-
                # kachel im Browser einzeln von Wikimedia nach.
                stored = await _download(downloader, logo["file_name"])
                await conn.execute(
                    LOGO_UPSERT, make, logo["file_name"], logo["page_url"],
                    logo["license"], logo["license_url"], logo["author"],
                    logo["width"], logo["height"], logo["wikidata_id"],
                    stored.get("image"), stored.get("content_type"),
                    stored.get("bytes"),
                )
                found += 1
            await conn.execute(LOOKUP_UPSERT, make, bool(logo))

            if index % 20 == 0:
                logger.info("  %s/%s Marken, %s Logos", index, len(makes), found)

    logger.info("Logo-Import fertig: %s Logos fuer %s Marken.", found, len(makes))
    return found


async def _download(client: httpx.AsyncClient, file_name: str) -> dict:
    """Das Logo als Bilddatei holen und ablegen.

    Logos sind meist SVG; Commons liefert daraus auf Wunsch ein PNG in
    fester Breite, das ueberall zuverlaessig darstellt.
    """
    from urllib.parse import quote

    url = COMMONS_FILE.format(name=quote(file_name), width=320)
    prepared = await fetch_and_prepare(client, url)
    return prepared or {}
