"""Importer: Fahrzeugbilder aus dem ADAC-Autokatalog.

Der Katalog ist nach Marke, Modell und Generation gegliedert und zeigt je
Generation eine Handvoll professioneller Aufnahmen aus verschiedenen
Richtungen. Genau das fehlte den Fotos aus Wikimedia Commons: dort sind es
Strassenaufnahmen wechselnder Qualitaet.

Zuordnung der Generation
------------------------
Die Adresse traegt die Generation im Klartext
(``/audi/a3/8v/``, ``/mercedes-benz/s-klasse/223/``), aber die Codes des
Katalogs sind nicht die Plattformcodes des Typenscheins - ein Abgleich
ueber die Zeichenfolge trifft munter daneben (``Passat 3C`` landete bei
``passat/b3``, Baujahr 1988). Deshalb entscheidet der **Bauzeitraum**: die
Modelluebersicht nennt zu jeder Generation die Jahre ("A3 8V 2012 - 2016"),
und gewaehlt wird die Generation mit der groessten Ueberschneidung zu
unserem Zeitraum. Ohne ausreichende Ueberschneidung wird nichts
uebernommen.

Rechtlicher Rahmen
------------------
Die robots.txt des ADAC schliesst den Autokatalog nicht aus und verweist
sogar auf eine eigene Sitemap dafuer. Die Bilder selbst sind fremdes
Urheberrecht - sie werden fuer den privaten, nicht oeffentlichen Betrieb
dieser Instanz abgelegt. Fuer eine Veroeffentlichung waere eine
Genehmigung des Rechteinhabers noetig. Quelle und Ursprungsseite werden
an jedem Bild mitgefuehrt.
"""

from __future__ import annotations

import logging
import re

import asyncpg
import httpx

from ..common import CachedClient
from .image_store import fetch_and_prepare

logger = logging.getLogger("etl.adac")

SITEMAP = "https://www.adac.de/sitemaps/sitemap-autokatalog.xml"
BASE = "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/"
#: Cloudinary liefert jede gewuenschte Breite; 1400 reicht fuer die Galerie.
ASSET = "https://assets.adac.de/image/upload/w_1400,c_limit,f_jpg,q_auto:good/v1/{path}"

#: TARGA schreibt Marken anders als der Katalog. Manche Marke steht dort
#: in zwei Bereichen: die Transporter von VW liegen unter
#: "vw-nutzfahrzeuge", die Pkw unter "vw" - beide werden probiert.
BRAND_SLUGS = {
    "VW": ["vw", "vw-nutzfahrzeuge"],
    "MERCEDES-BENZ": ["mercedes-benz"],
    "MERCEDES-AMG": ["mercedes-benz"],
    "ALFA ROMEO": ["alfa-romeo"],
    "LAND ROVER": ["land-rover"],
    "SKODA": ["skoda"],
    "CITROEN": ["citroen"],
    "OPEL/VAUXHALL": ["opel"],
    "DS": ["ds-automobiles"],
    "ROLLS ROYCE": ["rolls-royce"],
    "VW NUTZFAHRZEUGE": ["vw-nutzfahrzeuge", "vw"],
}

#: Der Katalog fuehrt manche Baureihe unter einem anderen Namen als der
#: Typenschein: die Generationen T4 bis T7 heissen dort schlicht
#: "Transporter", die Wohnmobilausbauten ebenso.
MODEL_SYNONYMS = {
    ("vw", "t4"): "transporter", ("vw", "t5"): "transporter",
    ("vw", "t6"): "transporter", ("vw", "t7"): "transporter",
    ("vw-nutzfahrzeuge", "t4"): "transporter",
    ("vw-nutzfahrzeuge", "t5"): "transporter",
    ("vw-nutzfahrzeuge", "t6"): "transporter",
    ("vw-nutzfahrzeuge", "t7"): "transporter",
    ("vw", "caravelle"): "transporter",
    ("vw", "california"): "transporter",
    ("vw", "multivan"): "transporter",
    ("vw-nutzfahrzeuge", "caravelle"): "transporter",
    ("vw-nutzfahrzeuge", "california"): "transporter",
    ("vw-nutzfahrzeuge", "multivan"): "transporter",
}

#: Link einer Generationskachel in der Modelluebersicht.
TILE_LINK = re.compile(
    r'href="/rund-ums-fahrzeug/autokatalog/marken-modelle/'
    r'(?P<brand>[^"/#]+)/(?P<model>[^"/#]+)/(?P<slug>[^"/#]+)/"'
)
#: Bauzeitraum einer Kachel - entweder abgeschlossen oder laufend.
TILE_YEARS = re.compile(
    r'(?:(?P<from>(?:19|20)\d{2})\s*[-\u2013]\s*(?P<to>(?:19|20)\d{2})'
    r'|seit\s+(?P<since>(?:19|20)\d{2}))'
)
#: Fahrzeugfoto im Katalog: "Autodatenbank/Fahrzeugbilder/im06160-2-mercedes-s-klasse.jpg"
PHOTO = re.compile(
    r"Autodatenbank/Fahrzeugbilder/(?P<id>im\d+)-(?P<index>\d+)-(?P<name>[a-z0-9-]+)\.(?:jpe?g|png|webp)",
    re.I,
)

IMAGE_INSERT = """
INSERT INTO vehicle_images (make, model_family, file_name, page_url, license,
                            license_url, author, description, width, height,
                            origin, score, image_year, platform, view,
                            source_url, image, thumb, content_type, bytes,
                            stored_at)
VALUES ($1, $2, $3, $4, $5, NULL, NULL, $6, NULL, NULL, 'adac', $7, NULL, $8,
        $9, $10, $11, $12, $13, $14, now())
-- Der eindeutige Index steht auf einem Ausdruck (coalesce ueber
-- platform); ohne Zielangabe greift er trotzdem.
ON CONFLICT DO NOTHING
"""

LOOKUP_UPSERT = """
INSERT INTO vehicle_image_lookups (make, model_family, platform, found, checked_at)
VALUES ($1, $2, $3, $4, now())
ON CONFLICT (make, model_family, coalesce(platform, '')) DO UPDATE
   SET found = EXCLUDED.found, checked_at = now()
"""

#: Alle Marken des Bestands - fuer den Abgleich mit dem Katalog.
ALL_MAKES_QUERY = """
SELECT DISTINCT make FROM type_approvals WHERE make IS NOT NULL AND make <> ''
"""

CATALOG_UPSERT = """
INSERT INTO brand_catalog (make, slug, models, updated_at)
VALUES ($1, $2, $3, now())
ON CONFLICT (make) DO UPDATE
   SET slug = EXCLUDED.slug, models = EXCLUDED.models, updated_at = now()
"""

GENERATIONS_QUERY = """
SELECT g.make, g.model_family AS family, g.platform, g.year_from, g.year_to,
       g.approvals AS n
FROM model_generations g
WHERE g.approvals >= $1
  AND ($3 = '' OR g.make = $3)
  AND NOT EXISTS (
      SELECT 1 FROM vehicle_image_lookups l
      WHERE l.make = g.make AND l.model_family = g.model_family
        AND coalesce(l.platform, '') = g.platform
        AND l.found > 0
  )
ORDER BY g.approvals DESC
LIMIT $2
"""


def brand_slugs(make: str) -> list[str]:
    """Bereiche des Katalogs, in denen diese Marke stehen kann."""
    cleaned = " ".join((make or "").strip().split())
    if cleaned.upper() in BRAND_SLUGS:
        return BRAND_SLUGS[cleaned.upper()]
    return [re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")]


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def model_candidates(models: set[str], family: str, brand: str = "") -> list[str]:
    """Modellseiten, die zu unserem Modellnamen passen.

    Erst exakt, dann mit Zusatz ("s" -> "s-klasse"). Eine lose Teilsuche
    waere gefaehrlich: "A3" steckt auch in "A3 Sportback e-tron".
    """
    want = normalise(family)
    if not want:
        return []
    synonym = MODEL_SYNONYMS.get((brand, want))
    if synonym and synonym in models:
        return [synonym]
    exact = [m for m in models if normalise(m) == want]
    if exact:
        return exact
    return sorted(
        m for m in models
        if normalise(m).startswith(want)
        and len(normalise(m)) <= len(want) + 7
    )


def overlap(a_from: int, a_to: int, b_from: int, b_to: int) -> int:
    return max(0, min(a_to, b_to) - max(a_from, b_from) + 1)


def pick_generation(tiles: list[dict], year_from: int, year_to: int) -> dict | None:
    """Die Katalog-Generation mit der groessten Ueberschneidung.

    Verlangt wird mehr als ein Streifjahr - sonst gewinnt die
    Nachbargeneration, die sich nur am Rand beruehrt.
    """
    best, best_score = None, 0
    for tile in tiles:
        score = overlap(tile["year_from"], tile["year_to"], year_from, year_to)
        if score > best_score:
            best, best_score = tile, score
    if best is None or best_score < 2:
        return None
    return best


def parse_tiles(html: str, brand: str, model: str) -> list[dict]:
    """Generationen einer Modellseite mit ihrem Bauzeitraum.

    Zwischen Link und Jahresangabe liegt der Bildabschnitt der Kachel -
    je nach Modell ueber tausend Zeichen. Ausgewertet wird deshalb der
    Bereich bis zur naechsten Kachel.
    """
    links = [
        m for m in TILE_LINK.finditer(html)
        if m.group("brand") == brand and m.group("model") == model
    ]
    out: dict[str, dict] = {}
    for position, link in enumerate(links):
        end = links[position + 1].start() if position + 1 < len(links) else len(html)
        years = TILE_YEARS.search(html, link.end(), end)
        if not years:
            continue
        if years.group("from"):
            year_from, year_to = int(years.group("from")), int(years.group("to"))
        else:
            # "seit 2024": laufende Baureihe, Ende offen
            year_from, year_to = int(years.group("since")), 2030
        if year_to < year_from:
            continue
        out.setdefault(
            link.group("slug"),
            {"slug": link.group("slug"), "year_from": year_from, "year_to": year_to},
        )
    return list(out.values())


def photo_paths(html: str, limit: int = 6) -> list[str]:
    """Die Fotos der Kachel-Galerie, ohne die Vergleichsfahrzeuge.

    Auf jeder Seite stehen auch Bilder konkurrierender Modelle. Sie
    gehoeren zu anderen Bild-IDs; die Galerie des Fahrzeugs selbst ist die
    haeufigste ID auf der Seite.
    """
    by_id: dict[str, dict[int, str]] = {}
    for match in PHOTO.finditer(html):
        by_id.setdefault(match.group("id"), {}).setdefault(
            int(match.group("index")), match.group(0)
        )
    if not by_id:
        return []
    main = max(by_id.values(), key=len)
    return [main[index] for index in sorted(main)][:limit]


async def _text(client: CachedClient, url: str, cache_key: str) -> str:
    response = await client.get_text(url, cache_key=cache_key)
    return response or ""


async def run(
    conn: asyncpg.Connection,
    *,
    min_approvals: int = 5,
    limit: int = 400,
    rate: float = 1.5,
    use_cache: bool = True,
    make: str = "",
) -> int:
    """Bilder der haeufigsten Generationen aus dem Autokatalog holen."""
    make = (make or "").strip().upper()
    rows = await conn.fetch(GENERATIONS_QUERY, min_approvals, limit, make)
    if not rows:
        logger.info("Keine offenen Generationen - nichts zu tun.")
        return 0

    logger.info("%s Generationen, %.1f s Abstand.", len(rows), rate)
    total = 0

    async with CachedClient(
        cache_name="adac", concurrency=1, min_interval=rate, use_cache=use_cache
    ) as client:
        sitemap = await _text(client, SITEMAP, "adac_sitemap")
        models: dict[str, set[str]] = {}
        # Die Fotos liegen auf den Fahrzeugseiten (vierte Ebene), nicht auf
        # der Generationsuebersicht. Deshalb wird zu jeder Generation eine
        # Fahrzeug-ID gemerkt.
        vehicles: dict[tuple[str, str, str], list[str]] = {}
        for loc in re.findall(r"<loc>(.*?)</loc>", sitemap):
            if not loc.startswith(BASE):
                continue
            parts = loc[len(BASE):].strip("/").split("/")
            if len(parts) == 4:
                models.setdefault(parts[0], set()).add(parts[1])
                vehicles.setdefault((parts[0], parts[1], parts[2]), []).append(parts[3])
        logger.info("Katalog: %s Marken, %s Generationen.", len(models), len(vehicles))

        # Festhalten, welche unserer Marken der Katalog kennt. Das Blaettern
        # nach Marke zeigt nur diese - Traktoren und Aufbauhersteller
        # gehoeren nicht in eine Fahrzeuguebersicht.
        known = 0
        for row in await conn.fetch(ALL_MAKES_QUERY):
            for slug in brand_slugs(row["make"]):
                if slug in models:
                    await conn.execute(
                        CATALOG_UPSERT, row["make"], slug, len(models[slug])
                    )
                    known += 1
                    break
        logger.info("%s unserer Marken stehen im Katalog.", known)

        async with httpx.AsyncClient(
            headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
            follow_redirects=True,
        ) as downloader:
            for index, row in enumerate(rows, start=1):
                found = await _one_generation(
                    conn, client, downloader, models, vehicles, row
                )
                total += found
                await conn.execute(
                    LOOKUP_UPSERT, row["make"], row["family"], row["platform"], found
                )
                if index % 25 == 0:
                    logger.info("  %s/%s, %s Bilder", index, len(rows), total)

    logger.info("ADAC-Bildimport fertig: %s Bilder fuer %s Generationen.",
                total, len(rows))
    return total


async def _one_generation(conn, client, downloader, models, vehicles, row) -> int:
    make, family, platform = row["make"], row["family"], row["platform"]
    if not row["year_from"] or not row["year_to"]:
        return 0

    pairs = [
        (brand, model)
        for brand in brand_slugs(make) if brand in models
        for model in model_candidates(models[brand], family, brand)
    ]
    for brand, model in pairs:
        try:
            html = await _text(
                client, f"{BASE}{brand}/{model}/", f"adac_model_{brand}_{model}"
            )
            tiles = parse_tiles(html, brand, model)
            generation = pick_generation(tiles, row["year_from"], row["year_to"])
            if generation is None:
                continue

            # Eine der Fahrzeugseiten dieser Generation traegt die Galerie.
            ids = vehicles.get((brand, model, generation["slug"]), [])
            paths, page = [], ""
            for vehicle_id in ids[:2]:
                page = f"{BASE}{brand}/{model}/{generation['slug']}/{vehicle_id}/"
                detail = await _text(
                    client, page,
                    f"adac_veh_{brand}_{model}_{generation['slug']}_{vehicle_id}",
                )
                paths = photo_paths(detail)
                if paths:
                    break
            if not paths:
                continue

            stored = 0
            for position, path in enumerate(paths):
                prepared = await fetch_and_prepare(
                    downloader, ASSET.format(path=path)
                )
                if prepared is None:
                    continue
                await conn.execute(
                    IMAGE_INSERT, make, family, path.split("/")[-1], page,
                    "ADAC Autokatalog",
                    f"{make} {family} ({generation['slug']})",
                    20 - position, platform, "exterior",
                    prepared["source_url"], prepared["image"], prepared["thumb"],
                    prepared["content_type"], prepared["bytes"],
                )
                stored += 1
            if stored:
                logger.debug("%s %s -> %s/%s (%s Bilder)",
                             make, family, model, generation["slug"], stored)
                return stored
        except Exception as exc:  # pragma: no cover - Netz/Format
            logger.warning("%s %s: %s", make, family, exc)
    return 0
