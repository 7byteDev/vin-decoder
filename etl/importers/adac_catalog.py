"""Importer: der Fahrzeugkatalog als Navigationsebene.

Marken, Modelle und Baureihen werden so uebernommen, wie der Katalog sie
gliedert - samt Markenlogo und Modellbild. Die Typengenehmigungen bleiben
davon unberuehrt; sie liefern weiterhin die technischen Daten und werden
unter die Katalogeintraege gehaengt.

Warum nicht aus den eigenen Daten ableiten? Weil das nicht funktioniert:
Der Modellname im Typenschein ist ein Freitext ("Q4 e-tron 40", "e-tron GT
quattro"), aus dem sich die Baureihe nicht zuverlaessig herausschneiden
laesst. Der Versuch, das erste Wort zu nehmen, hat "Q4 e-tron" unter "Q4"
einsortiert und "e-tron GT" unter "e-tron" - aus fuenf Baureihen wurde
eine.

Rechtlicher Rahmen wie beim Bildimport: die robots.txt schliesst den
Katalog nicht aus, die Inhalte sind fremdes Urheberrecht und werden fuer
den privaten, nicht oeffentlichen Betrieb dieser Instanz vorgehalten.
"""

from __future__ import annotations

import logging
import re

import asyncpg
import httpx

from ..common import CachedClient
from .image_store import fetch_and_prepare

logger = logging.getLogger("etl.catalog")

BASE = "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/"
BRANDS_URL = BASE + "?sort=NAME_ASC"
BRAND_URL = BASE + "{brand}/?sort=NAME_ASC&filter=NONE"
MODEL_URL = BASE + "{brand}/{model}/?sort=NAME_ASC&filter=NONE"
#: Cloudinary liefert jede Breite; mehr als 900 px braucht keine Kachel.
ASSET = "https://assets.adac.de/image/upload/w_{width},c_limit,f_jpg,q_auto:good/v1/{path}"

#: Eine Markenkachel der Uebersicht.
BRAND_TILE = re.compile(
    r'data-testid="carpages:brands:brand:link"\s+href="/rund-ums-fahrzeug/'
    r'autokatalog/marken-modelle/(?P<slug>[^"/?]+)/[^"]*"(?P<body>.*?)</a>',
    re.S,
)
#: Eine Modellkachel einer Markenseite.
MODEL_TILE = re.compile(
    r'data-tracking="\{&quot;click&quot;:\{&quot;element&quot;:&quot;'
    r'markeseite_baureihe&quot;,&quot;label&quot;:&quot;(?P<name>[^&]*)&quot;\}\}"'
    r'[^>]*href="/rund-ums-fahrzeug/autokatalog/marken-modelle/'
    r'(?P<brand>[^"/?]+)/(?P<slug>[^"/?]+)/[^"]*"(?P<body>.*?)</a>',
    re.S,
)
#: Eine Generationskachel einer Modellseite.
GENERATION_TILE = re.compile(
    r'href="/rund-ums-fahrzeug/autokatalog/marken-modelle/'
    r'(?P<brand>[^"/?]+)/(?P<model>[^"/?]+)/(?P<slug>[^"/?]+)/"(?P<body>.*?)</a>',
    re.S,
)

LOGO_PATH = re.compile(r"(Autodatenbank/Markenlogos/[^\"')\s?,\\]+)")
PHOTO_PATH = re.compile(r"(Autodatenbank/Fahrzeugbilder/[^\"')\s?,\\]+)")
NAME_TAG = re.compile(r">([^<>]{1,60})</p>")
COUNT_TAG = re.compile(r">(\d+)<!-- --> Generationen?<")
YEARS = re.compile(
    r"(?:(?P<from>(?:19|20)\d{2})\s*[-–]\s*(?P<to>(?:19|20)\d{2})"
    r"|seit\s+(?P<since>(?:19|20)\d{2}))"
)

BRAND_UPSERT = """
INSERT INTO catalog_brands (slug, name, logo, logo_thumb, models, updated_at)
VALUES ($1, $2, $3::bytea, $4::bytea, $5, now())
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name,
    logo = coalesce(EXCLUDED.logo, catalog_brands.logo),
    logo_thumb = coalesce(EXCLUDED.logo_thumb, catalog_brands.logo_thumb),
    models = greatest(EXCLUDED.models, catalog_brands.models),
    updated_at = now()
"""

MODEL_UPSERT = """
INSERT INTO catalog_models (brand_slug, slug, name, generations, image, thumb,
                            updated_at)
VALUES ($1, $2, $3, $4, $5::bytea, $6::bytea, now())
ON CONFLICT (brand_slug, slug) DO UPDATE SET
    name = EXCLUDED.name,
    generations = greatest(EXCLUDED.generations, catalog_models.generations),
    image = coalesce(EXCLUDED.image, catalog_models.image),
    thumb = coalesce(EXCLUDED.thumb, catalog_models.thumb),
    updated_at = now()
"""

GENERATION_UPSERT = """
INSERT INTO catalog_generations (brand_slug, model_slug, slug, name,
                                 year_from, year_to, image, thumb, updated_at)
VALUES ($1, $2, $3, $4, $5, $6, $7::bytea, $8::bytea, now())
ON CONFLICT (brand_slug, model_slug, slug) DO UPDATE SET
    name = EXCLUDED.name, year_from = EXCLUDED.year_from,
    year_to = EXCLUDED.year_to,
    image = coalesce(EXCLUDED.image, catalog_generations.image),
    thumb = coalesce(EXCLUDED.thumb, catalog_generations.thumb),
    updated_at = now()
"""


#: Reine Jahresangabe ("2021 - 2026", "seit 2024") - kein Name.
ONLY_YEARS = re.compile(r"^(?:seit\s+)?(?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)\d{2})?$")


def _text_after(body: str, *, first: bool = False) -> str:
    """Der sichtbare Name einer Kachel.

    Uebersprungen werden die Zeilen, die keine Namen sind: der
    Bauzeitraum und die Zahl der Generationen. Bei Generationskacheln
    steht der Name vor dem Zeitraum, bei Marken- und Modellkacheln
    dahinter.
    """
    names = [x.strip() for x in NAME_TAG.findall(body)]
    names = [
        x for x in names
        if x and "Generation" not in x and not ONLY_YEARS.match(" ".join(x.split()))
    ]
    if not names:
        return ""
    return names[0] if first else names[-1]


def parse_brands(html: str) -> list[dict]:
    """Marken der Uebersicht mit Logo-Pfad."""
    out: dict[str, dict] = {}
    for match in BRAND_TILE.finditer(html):
        body = match.group("body")
        logo = LOGO_PATH.search(body)
        out.setdefault(
            match.group("slug"),
            {
                "slug": match.group("slug"),
                "name": _text_after(body) or match.group("slug"),
                "logo": logo.group(1) if logo else "",
            },
        )
    return list(out.values())


def parse_models(html: str, brand: str) -> list[dict]:
    """Modelle einer Markenseite mit Bildpfad und Generationszahl."""
    out: dict[str, dict] = {}
    for match in MODEL_TILE.finditer(html):
        if match.group("brand") != brand:
            continue
        body = match.group("body")
        photo = PHOTO_PATH.search(body)
        count = COUNT_TAG.search(body)
        out.setdefault(
            match.group("slug"),
            {
                "slug": match.group("slug"),
                "name": (match.group("name") or "").strip() or match.group("slug"),
                "generations": int(count.group(1)) if count else 0,
                "image": photo.group(1) if photo else "",
            },
        )
    return list(out.values())


def _generation_name(label: str, slug: str) -> str:
    """Beschriftung einer Baureihe.

    Facelift-Kacheln tragen nur den Zusatz "(1. Facelift)"; der Code der
    Baureihe steht dann allein im Adressteil. Beides zusammen ergibt eine
    Bezeichnung, die auch aus der Liste heraus verstaendlich ist.
    """
    base = slug.split("-facelift")[0].upper()
    # Der Katalog nummeriert namenlose Baureihen im Adressteil
    # ("1generation"); in Grossbuchstaben liest sich das schlecht.
    numbered = re.match(r"^(\d+)GENERATION$", base)
    if numbered:
        base = f"{numbered.group(1)}. Generation"
    label = (label or "").strip()
    if not label:
        return base
    if label.startswith("("):
        return f"{base} {label}"
    return label


def parse_generations(html: str, brand: str, model: str) -> list[dict]:
    """Baureihen einer Modellseite mit Bauzeitraum und Bildpfad."""
    out: dict[str, dict] = {}
    for match in GENERATION_TILE.finditer(html):
        if match.group("brand") != brand or match.group("model") != model:
            continue
        body = match.group("body")
        years = YEARS.search(body)
        if years is None:
            continue
        if years.group("from"):
            year_from, year_to = int(years.group("from")), int(years.group("to"))
        else:
            year_from, year_to = int(years.group("since")), None
        photo = PHOTO_PATH.search(body)
        out.setdefault(
            match.group("slug"),
            {
                "slug": match.group("slug"),
                "name": _generation_name(
                    _text_after(body, first=True), match.group("slug")
                ),
                "year_from": year_from,
                "year_to": year_to,
                "image": photo.group(1) if photo else "",
            },
        )
    return list(out.values())


async def _have(conn, query: str, *args) -> bool:
    """Liegt das Bild schon vor? Ein Neustart soll nicht alles neu laden."""
    return bool(await conn.fetchval(query, *args))


HAVE_BRAND = "SELECT logo_thumb IS NOT NULL FROM catalog_brands WHERE slug = $1"
HAVE_MODEL = (
    "SELECT thumb IS NOT NULL FROM catalog_models"
    " WHERE brand_slug = $1 AND slug = $2"
)
HAVE_GENERATION = (
    "SELECT thumb IS NOT NULL FROM catalog_generations"
    " WHERE brand_slug = $1 AND model_slug = $2 AND slug = $3"
)


async def _picture(
    client: httpx.AsyncClient, path: str, *, width: int, thumb: int
) -> dict:
    if not path:
        return {}
    prepared = await fetch_and_prepare(
        client, ASSET.format(width=width, path=path),
        full_width=width, thumb_width=thumb,
    )
    return prepared or {}


async def run(
    conn: asyncpg.Connection,
    *,
    rate: float = 1.2,
    use_cache: bool = True,
    brand: str = "",
    with_generations: bool = True,
) -> int:
    """Katalog einlesen: Marken, Modelle und Baureihen."""
    async with CachedClient(
        cache_name="adac_catalog", concurrency=1, min_interval=rate,
        use_cache=use_cache,
    ) as pages, httpx.AsyncClient(
        headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
        follow_redirects=True,
    ) as files:
        overview = await pages.get_text(BRANDS_URL, cache_key="cat_brands") or ""
        brands = parse_brands(overview)
        if brand:
            brands = [b for b in brands if b["slug"] == brand]
        logger.info("Katalog: %s Marken.", len(brands))

        models_total = 0
        generations_total = 0
        for index, entry in enumerate(brands, start=1):
            logo = (
                {}
                if await _have(conn, HAVE_BRAND, entry["slug"])
                else await _picture(files, entry["logo"], width=320, thumb=96)
            )
            page = await pages.get_text(
                BRAND_URL.format(brand=entry["slug"]),
                cache_key=f"cat_brand_{entry['slug']}",
            ) or ""
            models = parse_models(page, entry["slug"])
            await conn.execute(
                BRAND_UPSERT, entry["slug"], entry["name"],
                logo.get("image"), logo.get("thumb"), len(models),
            )

            for model in models:
                picture = (
                    {}
                    if await _have(conn, HAVE_MODEL, entry["slug"], model["slug"])
                    else await _picture(files, model["image"], width=900, thumb=400)
                )
                await conn.execute(
                    MODEL_UPSERT, entry["slug"], model["slug"], model["name"],
                    model["generations"], picture.get("image"), picture.get("thumb"),
                )
                models_total += 1

                if with_generations:
                    found = await _generations(
                        conn, pages, files, entry["slug"], model["slug"]
                    )
                    generations_total += found
                    # Die Kachel nennt die Zahl nicht immer; dann zaehlt,
                    # was die Modellseite tatsaechlich auflistet.
                    if found and not model["generations"]:
                        await conn.execute(
                            "UPDATE catalog_models SET generations = $3"
                            " WHERE brand_slug = $1 AND slug = $2",
                            entry["slug"], model["slug"], found,
                        )

            logger.info(
                "  %s/%s %s: %s Modelle", index, len(brands), entry["slug"],
                len(models),
            )

    logger.info(
        "Katalog fertig: %s Marken, %s Modelle, %s Baureihen.",
        len(brands), models_total, generations_total,
    )
    return models_total


async def _generations(conn, pages, files, brand: str, model: str) -> int:
    """Baureihen eines Modells uebernehmen."""
    html = await pages.get_text(
        MODEL_URL.format(brand=brand, model=model),
        cache_key=f"cat_model_{brand}_{model}",
    ) or ""
    generations = parse_generations(html, brand, model)
    for generation in generations:
        picture = (
            {}
            if await _have(conn, HAVE_GENERATION, brand, model, generation["slug"])
            else await _picture(files, generation["image"], width=900, thumb=400)
        )
        await conn.execute(
            GENERATION_UPSERT, brand, model, generation["slug"], generation["name"],
            generation["year_from"], generation["year_to"],
            picture.get("image"), picture.get("thumb"),
        )
    return len(generations)
