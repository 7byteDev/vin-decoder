"""Bereits erfasste Bilder nachtraeglich in die Datenbank holen.

Die Wikimedia-Importe haben nur Adressen gespeichert; die Detailseite lud
jedes Foto beim Aufruf von dort. Das ist langsam und haengt von einem
fremden Dienst ab. Dieser Lauf holt alles nach, was noch keine Datei hat.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote

import asyncpg
import httpx

from .image_store import fetch_and_prepare

logger = logging.getLogger("etl.images.backfill")

COMMONS_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=1400"
#: Logos brauchen keine grosse Breite - sie stehen in einer Kachel.
LOGO_FILE = "https://commons.wikimedia.org/wiki/Special:FilePath/{name}?width=320"

PENDING_QUERY = """
SELECT id, file_name FROM vehicle_images
WHERE image IS NULL AND origin <> 'adac'
ORDER BY score DESC
LIMIT $1
"""

PENDING_LOGOS = """
SELECT make, file_name FROM brand_logos WHERE image IS NULL OR thumb IS NULL
"""

STORE_LOGO = """
UPDATE brand_logos
   SET image = $2, thumb = $3, content_type = $4, bytes = $5, stored_at = now()
 WHERE make = $1
"""

STORE = """
UPDATE vehicle_images
   SET image = $2, thumb = $3, content_type = $4, bytes = $5,
       source_url = $6, stored_at = now()
 WHERE id = $1
"""


async def run(
    conn: asyncpg.Connection, *, limit: int = 500, rate: float = 1.0
) -> int:
    """Fehlende Bilddateien nachladen."""
    rows = await conn.fetch(PENDING_QUERY, limit)
    if not rows:
        logger.info("Alle Bilder liegen bereits vor.")
        return 0

    logger.info("%s Bilder werden nachgeladen.", len(rows))
    stored = 0
    async with httpx.AsyncClient(
        headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
        follow_redirects=True,
    ) as client:
        for index, row in enumerate(rows, start=1):
            url = COMMONS_FILE.format(name=quote(row["file_name"]))
            await asyncio.sleep(max(0.0, rate))
            prepared = await fetch_and_prepare(client, url)
            if prepared:
                await conn.execute(
                    STORE, row["id"], prepared["image"], prepared["thumb"],
                    prepared["content_type"], prepared["bytes"],
                    prepared["source_url"],
                )
                stored += 1
            if index % 50 == 0:
                logger.info("  %s/%s, %s abgelegt", index, len(rows), stored)

    logger.info("Nachladen fertig: %s von %s Bildern.", stored, len(rows))
    return stored


async def run_logos(conn: asyncpg.Connection) -> int:
    """Markenlogos nachladen, die noch keine Datei haben.

    Der Logo-Import laeuft ueber Wikidata und ist entsprechend langsam;
    hier geht es nur noch um die Dateien zu bereits bekannten Logos.
    """
    rows = await conn.fetch(PENDING_LOGOS)
    if not rows:
        logger.info("Alle Logos liegen bereits vor.")
        return 0

    logger.info("%s Logos werden nachgeladen.", len(rows))
    stored = 0
    async with httpx.AsyncClient(
        headers={"User-Agent": "vin-decoder/1.0 (privater Betrieb)"},
        follow_redirects=True,
    ) as client:
        for index, row in enumerate(rows):
            # Ohne Abstand antwortet Commons nach kurzer Zeit mit 429 und
            # der halbe Lauf geht leer aus.
            if index:
                await asyncio.sleep(0.7)
            url = LOGO_FILE.format(name=quote(row["file_name"]))
            prepared = await fetch_and_prepare(client, url, thumb_width=96)
            if prepared:
                await conn.execute(
                    STORE_LOGO, row["make"], prepared["image"], prepared["thumb"],
                    prepared["content_type"], prepared["bytes"],
                )
                stored += 1
    logger.info("Logos fertig: %s von %s.", stored, len(rows))
    return stored
