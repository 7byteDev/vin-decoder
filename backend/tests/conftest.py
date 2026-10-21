"""Test-Setup: Backend importierbar machen, Live-Abfragen abschalten."""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))  # damit auch etl.* importierbar ist

# Tests laufen ohne Netz und ohne Datenbank.
os.environ.setdefault("ENABLE_LIVE_NHTSA", "false")
os.environ.setdefault("DATABASE_URL", "")
os.environ.setdefault("LOG_LOOKUPS", "false")


@pytest.fixture(scope="session")
def project_root() -> pathlib.Path:
    return ROOT


@pytest.fixture
def client():
    from app.config import get_settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
