"""Gemeinsame Bausteine der ETL-Pipeline.

Jeder Importer ist wiederholbar (idempotent): er schreibt mit ON CONFLICT
und aktualisiert am Ende den Zaehler und Zeitstempel in ``sources``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
import re
from collections.abc import Iterable
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger("etl")

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "etl" / "data" / "raw"
DATA_DIR = ROOT / "etl" / "data"


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )


def dsn_from_env() -> str:
    dsn = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or ""
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


async def connect() -> asyncpg.Connection:
    dsn = dsn_from_env()
    if not dsn:
        raise SystemExit(
            "DATABASE_URL_SYNC (oder DATABASE_URL) ist nicht gesetzt - siehe .env.example"
        )
    return await asyncpg.connect(dsn)


async def source_id(conn: asyncpg.Connection, key: str) -> int:
    row = await conn.fetchrow(
        "SELECT id, license_ok FROM sources WHERE key = $1", key
    )
    if row is None:
        raise SystemExit(
            f"Quelle '{key}' fehlt in der Tabelle sources - "
            "erst db/migrations/002_seed_sources.sql einspielen."
        )
    if not row["license_ok"]:
        raise SystemExit(
            f"Quelle '{key}' ist als nicht importierbar markiert "
            "(license_ok = false). Import abgebrochen."
        )
    return row["id"]


async def finish_source(conn: asyncpg.Connection, key: str, count: int) -> None:
    await conn.execute(
        "UPDATE sources SET last_import_at = now(), record_count = $2 WHERE key = $1",
        key,
        count,
    )


# ---------------------------------------------------------------------------
# HTTP mit Cache auf Platte (macht Wiederholungslaeufe billig)
# ---------------------------------------------------------------------------


class RateLimited(RuntimeError):
    """Die Gegenstelle hat uns ausgesperrt (403/429)."""


class CachedClient:
    """HTTP-Client mit Plattencache und hoeflicher Taktung.

    Die Voreinstellungen sind bewusst zurueckhaltend: eine Anfrage pro
    Sekunde, zwei parallele Verbindungen. Ein frueherer Lauf mit acht
    parallelen Verbindungen ohne Pause hat die oeffentliche IP bei vPIC
    nach rund 500 Anfragen in eine 403-Sperre laufen lassen. Bei
    anhaltenden Sperrantworten bricht der Lauf sauber ab, statt weiter
    gegen die Wand zu fahren - der Cache bleibt erhalten, ein spaeterer
    Lauf setzt dort auf.
    """

    def __init__(
        self,
        *,
        cache_name: str,
        concurrency: int = 2,
        timeout: float = 20.0,
        use_cache: bool = True,
        min_interval: float = 1.0,
        max_consecutive_blocks: int = 3,
    ) -> None:
        self._dir = RAW_DIR / cache_name
        self._dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._client = httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": "vin-decoder-etl/0.1 (+ukm.net.tr)"}
        )
        self._use_cache = use_cache
        self._min_interval = max(0.0, min_interval)
        self._pace_lock = asyncio.Lock()
        self._next_slot = 0.0
        self._consecutive_blocks = 0
        self._max_consecutive_blocks = max_consecutive_blocks

    async def _pace(self) -> None:
        """Sorgt fuer den Mindestabstand zwischen zwei Anfragen."""
        if self._min_interval <= 0:
            return
        async with self._pace_lock:
            now = asyncio.get_running_loop().time()
            wait = self._next_slot - now
            self._next_slot = max(now, self._next_slot) + self._min_interval
        if wait > 0:
            await asyncio.sleep(wait)

    async def __aenter__(self) -> CachedClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    def _path(self, name: str) -> pathlib.Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:120]
        return self._dir / f"{safe}.json"

    async def get_text(self, url: str, *, cache_key: str) -> str | None:
        """Eine HTML-Seite holen - gleiche Pacing- und Sperrlogik wie get_json.

        Der Autokatalog liefert HTML, kein JSON. Der Cache liegt daneben,
        damit ein abgebrochener Lauf nicht alles neu ziehen muss.
        """
        path = self._path(cache_key).with_suffix(".html")
        if self._use_cache and path.exists():
            return path.read_text(encoding="utf-8")

        async with self._semaphore:
            for attempt in range(4):
                await self._pace()
                try:
                    response = await self._client.get(url, follow_redirects=True)
                except Exception as exc:
                    if attempt == 3:
                        logger.warning("Abruf fehlgeschlagen: %s (%s)", url, exc)
                        return None
                    await asyncio.sleep(2 ** attempt)
                    continue

                if response.status_code in (403, 429, 503):
                    self._consecutive_blocks += 1
                    if self._consecutive_blocks >= self._max_consecutive_blocks:
                        raise RateLimited(
                            f"{response.status_code} von {url} - die Gegenstelle sperrt uns "
                            f"aus. Lauf abgebrochen, der Cache bleibt erhalten."
                        )
                    backoff = min(120, 15 * self._consecutive_blocks)
                    logger.warning("%s erhalten, warte %ss", response.status_code, backoff)
                    await asyncio.sleep(backoff)
                    return None

                self._consecutive_blocks = 0
                if response.status_code >= 400:
                    logger.warning("HTTP %s fuer %s", response.status_code, url)
                    return None

                text = response.text
                if self._use_cache:
                    path.write_text(text, encoding="utf-8")
                return text
        return None

    async def get_json(self, url: str, *, cache_key: str, params: dict | None = None) -> Any:
        path = self._path(cache_key)
        if self._use_cache and path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                path.unlink(missing_ok=True)

        async with self._semaphore:
            payload = None
            for attempt in range(4):
                await self._pace()
                try:
                    response = await self._client.get(url, params=params)
                except Exception as exc:
                    if attempt == 3:
                        logger.warning("Abruf fehlgeschlagen: %s (%s)", url, exc)
                        return None
                    await asyncio.sleep(2 ** attempt)
                    continue

                if response.status_code in (403, 429, 503):
                    # Wichtig: ein 429 wird NICHT als Fehlversuch wiederholt.
                    # Genau das hat den Lauf gegen Wikimedia zum Problem
                    # gemacht - jede geblockte Anfrage wurde viermal
                    # gestellt und hat die Drosselung weiter angeheizt.
                    self._consecutive_blocks += 1
                    if self._consecutive_blocks >= self._max_consecutive_blocks:
                        raise RateLimited(
                            f"{response.status_code} von {url.split('/api/')[0]} - die Gegenstelle "
                            f"sperrt uns aus. Lauf abgebrochen, der Cache bleibt erhalten. "
                            f"Spaeter mit groesserem --rate erneut starten."
                        )
                    backoff = min(120, 15 * self._consecutive_blocks)
                    logger.warning(
                        "%s erhalten, warte %ss (%s/%s in Folge)",
                        response.status_code, backoff,
                        self._consecutive_blocks, self._max_consecutive_blocks,
                    )
                    await asyncio.sleep(backoff)
                    return None

                self._consecutive_blocks = 0
                if response.status_code >= 400:
                    logger.warning("HTTP %s fuer %s", response.status_code, url)
                    return None
                try:
                    payload = response.json()
                except ValueError:
                    logger.warning("Keine gueltige JSON-Antwort: %s", url)
                    return None
                break

            if payload is None:
                return None

        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload


# ---------------------------------------------------------------------------
# Laendernormalisierung (vPIC liefert Klartextnamen wie "UNITED STATES (USA)")
# ---------------------------------------------------------------------------

COUNTRY_TO_ISO: dict[str, str] = {
    "ARGENTINA": "AR", "AUSTRALIA": "AU", "AUSTRIA": "AT", "BELARUS": "BY",
    "BELGIUM": "BE", "BRAZIL": "BR", "BULGARIA": "BG", "CANADA": "CA",
    "CHILE": "CL", "CHINA": "CN", "COLOMBIA": "CO", "CROATIA": "HR",
    "CZECH REPUBLIC": "CZ", "CZECHIA": "CZ", "DENMARK": "DK", "EGYPT": "EG",
    "ESTONIA": "EE", "FINLAND": "FI", "FRANCE": "FR", "GERMANY": "DE",
    "GREECE": "GR", "HUNGARY": "HU", "INDIA": "IN", "INDONESIA": "ID",
    "IRAN": "IR", "IRELAND": "IE", "ISRAEL": "IL", "ITALY": "IT",
    "JAPAN": "JP", "KAZAKHSTAN": "KZ", "KOREA (SOUTH)": "KR",
    "SOUTH KOREA": "KR", "KOREA, REPUBLIC OF": "KR", "LATVIA": "LV",
    "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MALAYSIA": "MY", "MALTA": "MT",
    "MEXICO": "MX", "MOROCCO": "MA", "NETHERLANDS": "NL", "NEW ZEALAND": "NZ",
    "NIGERIA": "NG", "NORWAY": "NO", "PAKISTAN": "PK", "PERU": "PE",
    "PHILIPPINES": "PH", "POLAND": "PL", "PORTUGAL": "PT", "ROMANIA": "RO",
    "RUSSIA": "RU", "RUSSIAN FEDERATION": "RU", "SAUDI ARABIA": "SA",
    "SERBIA": "RS", "SINGAPORE": "SG", "SLOVAKIA": "SK", "SLOVENIA": "SI",
    "SOUTH AFRICA": "ZA", "SPAIN": "ES", "SRI LANKA": "LK", "SWEDEN": "SE",
    "SWITZERLAND": "CH", "TAIWAN": "TW", "THAILAND": "TH", "TUNISIA": "TN",
    "TURKEY": "TR", "TURKIYE": "TR", "UKRAINE": "UA",
    "UNITED ARAB EMIRATES": "AE", "UNITED KINGDOM": "GB",
    "UNITED STATES": "US", "URUGUAY": "UY", "VENEZUELA": "VE", "VIETNAM": "VN",
}

EU_CODES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE",
}
EUROPE_CODES = EU_CODES | {"GB", "CH", "NO", "RS", "UA", "BY", "RU"}


def normalize_country(name: str | None) -> tuple[str | None, str | None, str | None]:
    """('GERMANY') -> ('Germany', 'DE', 'EU'). Unbekannt -> (name, None, None)."""
    if not name:
        return None, None, None
    cleaned = re.sub(r"\s*\(.*?\)\s*", " ", name).strip().upper()
    iso = COUNTRY_TO_ISO.get(cleaned)
    if iso is None:
        return name.title(), None, None
    if iso == "TR":
        region = "TR"
    elif iso in EUROPE_CODES:
        region = "EU"
    elif iso in {"US", "CA", "MX"}:
        region = "NA"
    else:
        region = None
    return cleaned.title(), iso, region


def chunked(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    batch: list[Any] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
