"""FastAPI-Anwendung des VIN-Decoders.

Startverhalten: ist eine Datenbank erreichbar, laeuft die API im Vollmodus.
Ist sie es nicht, bleibt die API im Nur-Struktur-Modus benutzbar - die
deterministische Decodierung nach ISO 3779 braucht keine Datenbank.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import VERSION, health, router
from .config import get_settings
from .db import Database
from .decoder.structural import VinFormatError
from .sources.db_provider import DatabaseProvider
from .sources.nhtsa import NhtsaProvider
from .sources.type_approval import TypeApprovalProvider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    db = Database(settings.asyncpg_dsn)
    await db.connect()

    client = httpx.AsyncClient(timeout=settings.nhtsa_timeout_seconds)

    app.state.settings = settings
    app.state.db = db
    app.state.http = client
    type_approval = TypeApprovalProvider(db)
    app.state.type_approval_provider = type_approval
    app.state.db_providers = [DatabaseProvider(db), type_approval]
    app.state.live_providers = (
        [
            NhtsaProvider(
                base_url=settings.nhtsa_base_url,
                timeout=settings.nhtsa_timeout_seconds,
                client=client,
            )
        ]
        if settings.enable_live_nhtsa
        else []
    )

    try:
        yield
    finally:
        await client.aclose()
        await db.disconnect()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VIN-Decoder API",
        version=VERSION,
        summary="Technischer VIN-Decoder mit Konfidenz- und Quellenangabe (EU/TR-Fokus)",
        description=(
            "Verarbeitet ausschliesslich technische Fahrzeugdaten. "
            "Es werden keine personenbezogenen Daten oder Halterinformationen "
            "verarbeitet, gespeichert oder ausgegeben."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # --- einfache Ratenbegrenzung -----------------------------------------
    # Nur im Speicher, Schluessel ist ein gehashtes IP-Praefix. Es wird nichts
    # davon persistiert - die Begrenzung schuetzt nur vor Dauerlast.
    buckets: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        limit = settings.decode_rate_limit_per_minute
        if limit <= 0 or not request.url.path.startswith("/api/v1/decode"):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        key = hashlib.sha256(client_host.encode()).hexdigest()[:16]
        now = time.monotonic()
        bucket = buckets[key]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": f"Too many requests, limit is {limit}/minute.",
                        "detail": {},
                    }
                },
            )
        bucket.append(now)
        return await call_next(request)

    @app.exception_handler(VinFormatError)
    async def vin_format_error_handler(_: Request, exc: VinFormatError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": exc.code, "message": str(exc), "detail": exc.detail}
            },
        )

    app.include_router(router, prefix="/api/v1")

    @app.get("/health", include_in_schema=False)
    async def root_health(request: Request):
        """Kurzform fuer Loadbalancer/Monitoring (identisch zu /api/v1/health)."""
        return await health(request)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"service": "vin-decoder-api", "version": VERSION, "docs": "/docs"}

    return app


app = create_app()
