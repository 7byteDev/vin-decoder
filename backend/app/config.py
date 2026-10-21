"""Konfiguration aus Umgebungsvariablen (.env)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Datenbank ---------------------------------------------------------
    # Leer lassen = API laeuft im Nur-Struktur-Modus (ohne eigene DB).
    database_url: str = ""

    # --- API ---------------------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # --- Live-Quellen ------------------------------------------------------
    enable_live_nhtsa: bool = True
    nhtsa_base_url: str = "https://vpic.nhtsa.dot.gov/api/vehicles"
    nhtsa_timeout_seconds: float = 6.0

    # --- Betrieb -----------------------------------------------------------
    log_lookups: bool = True
    decode_rate_limit_per_minute: int = 60

    @property
    def asyncpg_dsn(self) -> str:
        """asyncpg erwartet ein reines ``postgresql://``-DSN."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
