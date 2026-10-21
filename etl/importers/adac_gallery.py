"""Importer: Bildergalerie je Katalog-Baureihe.

Die Kachel des Katalogs zeigt ein Bild. Auf der Fahrzeugseite darunter
liegen fuenf bis sechs Aufnahmen aus verschiedenen Richtungen - das ist
die Galerie, die auf der Detailseite gebraucht wird.

Der Weg dorthin: Baureihenseite aufrufen, die erste Fahrzeug-Adresse
herausnehmen, deren Seite laden und die Bilder der Galerie einsammeln. Von
den Vergleichsfahrzeugen, die dieselbe Seite zeigt, unterscheidet sie sich
durch die Bild-Kennung - die des eigenen Fahrzeugs kommt am haeufigsten
vor.

Geholt werden nur Baureihen, zu denen wir auch Typengenehmigungen haben.
Der Katalog reicht bis in die Sechziger; Bilder fuer Fahrzeuge, die wir
gar nicht fuehren, waeren verschenkte Anfragen.
"""

from __future__ import annotations

import logging
import re

import asyncpg
import httpx

from ..common import CachedClient
from .adac_images import ASSET, BASE, photo_paths
from .image_store import fetch_and_prepare

logger = logging.getLogger("etl.gallery")

GENERATION_URL = BASE + "{brand}/{model}/{generation}/"
#: Adresse einer Fahrzeugseite unterhalb der Baureihe.
VEHICLE_LINK = re.compile(
    r'href="/rund-ums-fahrzeug/autokatalog/marken-modelle/'
    r'(?P<brand>[^"/?]+)/(?P<model>[^"/?]+)/(?P<generation>[^"/?]+)/(?P<id>\d+)/"'
)

PENDING_QUERY = """
SELECT g.brand_slug, g.model_slug, g.slug,
       count(a.approval_id) AS fahrzeuge
FROM catalog_generations g
JOIN approval_catalog a
  ON a.brand_slug = g.brand_slug AND a.model_slug = g.model_slug
 AND a.generation_slug = g.slug
WHERE NOT EXISTS (
    SELECT 1 FROM catalog_generation_images i
     WHERE i.brand_slug = g.brand_slug AND i.model_slug = g.model_slug
       AND i.generation_slug = g.slug
)
GROUP BY 1, 2, 3
ORDER BY count(a.approval_id) DESC
LIMIT $1
"""

IMAGE_UPSERT = """
INSERT INTO catalog_generation_images (brand_slug, model_slug, generation_slug,
                                       position, file_name, source_url,
                                       image, thumb)
VALUES ($1, $2, $3, $4, $5, $6, $7::bytea, $8::bytea)
ON CONFLICT (brand_slug, model_slug, generation_slug, position) DO UPDATE SET
    file_name = EXCLUDED.file_name, source_url = EXCLUDED.source_url,
    image = EXCLUDED.image, thumb = EXCLUDED.thumb, imported_at = now()
"""

#: Platzhalterzeile, damit eine erfolglose Baureihe nicht erneut abgefragt
#: wird. Sie traegt keine Bilddaten und wird beim Ausliefern uebersprungen.
EMPTY_MARK = """
INSERT INTO catalog_generation_images (brand_slug, model_slug, generation_slug,
                                       position, file_name)
VALUES ($1, $2, $3, 0, '')
ON CONFLICT DO NOTHING
"""


async def run(
    conn: asyncpg.Connection,
    *,
    limit: int = 400,
    rate: float = 1.0,
    use_cache: bool = True,
    keep: int = 6,
) -> int:
    """Galerien der meistgenutzten Baureihen nachladen."""
    rows = await conn.fetch(PENDING_QUERY, limit)
    if not rows:
        logger.info("Alle Baureihen haben eine Galerie.")
        return 0

    logger.info("%s Baureihen werden geholt (%.1f s Abstand).", len(rows), rate)
    total = 0

    async with CachedClient(
        cache_name="adac_gallery", concurrency=1, min_interval=rate,
        use_cache=use_cache,
    ) as pages, httpx.AsyncClient(
        headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
        follow_redirects=True,
    ) as files:
        for index, row in enumerate(rows, start=1):
            brand, model, generation = (
                row["brand_slug"], row["model_slug"], row["slug"]
            )
            stored = 0
            try:
                stored = await _one(
                    conn, pages, files, brand, model, generation, keep
                )
            except Exception as exc:  # pragma: no cover - Netz/Format
                logger.warning("%s/%s/%s: %s", brand, model, generation, exc)

            if stored == 0:
                await conn.execute(EMPTY_MARK, brand, model, generation)
            total += stored
            if index % 25 == 0:
                logger.info("  %s/%s, %s Bilder", index, len(rows), total)

    logger.info("Galerien fertig: %s Bilder fuer %s Baureihen.", total, len(rows))
    return total


async def _one(conn, pages, files, brand, model, generation, keep) -> int:
    """Eine Baureihe: Fahrzeugseite finden, Bilder holen, ablegen."""
    listing = await pages.get_text(
        GENERATION_URL.format(brand=brand, model=model, generation=generation),
        cache_key=f"gal_gen_{brand}_{model}_{generation}",
    ) or ""
    vehicle = next(
        (
            m.group("id")
            for m in VEHICLE_LINK.finditer(listing)
            if m.group("brand") == brand and m.group("model") == model
            and m.group("generation") == generation
        ),
        None,
    )
    if vehicle is None:
        return 0

    detail = await pages.get_text(
        GENERATION_URL.format(brand=brand, model=model, generation=generation)
        + f"{vehicle}/",
        cache_key=f"gal_veh_{brand}_{model}_{generation}_{vehicle}",
    ) or ""
    paths = photo_paths(detail, limit=keep)

    stored = 0
    for position, path in enumerate(paths, start=1):
        prepared = await fetch_and_prepare(
            files, ASSET.format(path=path), full_width=1400, thumb_width=400
        )
        if prepared is None:
            continue
        await conn.execute(
            IMAGE_UPSERT, brand, model, generation, position,
            path.split("/")[-1], prepared["source_url"],
            prepared["image"], prepared["thumb"],
        )
        stored += 1
    return stored
