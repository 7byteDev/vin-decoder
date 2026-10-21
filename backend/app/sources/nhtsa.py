"""Provider: Live-Nachfrage bei der NHTSA-vPIC-API.

Sekundaerquelle laut Projektplan. Fuer nordamerikanische Fahrzeuge ist vPIC
sehr zuverlaessig, fuer rein europaeische Modelle liefert es oft nur
Hersteller, Marke, Baujahr und Werk - aber kein Modell. Genau deshalb wird
das Ergebnis regionsabhaengig gewichtet.
"""

from __future__ import annotations

import logging
import time

import httpx

from ..decoder.structural import StructuralResult
from ..decoder.types import Attr, Candidate, ProviderResult

#: vPIC-Feld -> Attributname
FIELD_MAP: dict[str, str] = {
    "Manufacturer": Attr.MANUFACTURER,
    "Make": Attr.MAKE,
    "Model": Attr.MODEL,
    "Series": Attr.SERIES,
    "Trim": Attr.TRIM,
    "ModelYear": Attr.MODEL_YEAR,
    "VehicleType": Attr.VEHICLE_TYPE,
    "BodyClass": Attr.BODY_CLASS,
    "FuelTypePrimary": Attr.FUEL_TYPE,
    "DisplacementL": Attr.ENGINE_DISPLACEMENT_L,
    "EngineCylinders": Attr.ENGINE_CYLINDERS,
    "EngineKW": Attr.ENGINE_POWER_KW,
    "EngineModel": Attr.ENGINE_MODEL,
    "DriveType": Attr.DRIVE_TYPE,
    "TransmissionStyle": Attr.TRANSMISSION,
    "Doors": Attr.DOORS,
    "Seats": Attr.SEATS,
    "PlantCity": Attr.PLANT_CITY,
    "PlantCountry": Attr.PLANT_COUNTRY,
    "PlantCompanyName": Attr.PLANT_COMPANY,
}

NUMERIC_ATTRIBUTES = {
    Attr.MODEL_YEAR,
    Attr.ENGINE_CYLINDERS,
    Attr.ENGINE_POWER_KW,
    Attr.DOORS,
    Attr.SEATS,
}

#: Platzhalter, die vPIC statt eines leeren Feldes liefert.
PLACEHOLDERS = {"", "not applicable", "n/a", "na", "unknown", "0"}


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if text.casefold() in PLACEHOLDERS else text


logger = logging.getLogger(__name__)


class NhtsaProvider:
    """Fragt ``DecodeVinValues`` ab und uebersetzt das Ergebnis in Kandidaten.

    Mit Sicherung (Circuit Breaker): haeuft sich der Fehler, wird die Quelle
    voruebergehend uebersprungen, statt bei jeder Anfrage erneut in dieselbe
    Wand zu laufen. Das schuetzt die Antwortzeit der eigenen API und
    verhindert, dass wir eine Sperre der Gegenstelle weiter verlaengern.
    """

    key = "nhtsa_vpic"

    def __init__(
        self,
        base_url: str = "https://vpic.nhtsa.dot.gov/api/vehicles",
        timeout: float = 6.0,
        client: httpx.AsyncClient | None = None,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._failures = 0
        self._open_until = 0.0

    @property
    def circuit_open(self) -> bool:
        return time.monotonic() < self._open_until

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._open_until = time.monotonic() + self._cooldown
            logger.warning(
                "NHTSA vPIC nach %s Fehlern fuer %.0fs uebersprungen.",
                self._failures, self._cooldown,
            )

    def _record_success(self) -> None:
        self._failures = 0
        self._open_until = 0.0

    def _region_weight(self, structural: StructuralResult) -> float:
        """vPIC ist fuer NA stark, fuer Europa/Tuerkei nur ergaenzend."""
        if structural.region_code == "NA":
            return 1.0
        if structural.in_primary_focus:
            return 0.62
        return 0.75

    async def fetch(self, structural: StructuralResult) -> ProviderResult:
        started = time.perf_counter()
        if self.circuit_open:
            return ProviderResult(source=self.key, used=False, error="circuit_open")

        url = f"{self._base_url}/DecodeVinValues/{structural.vin}"
        params = {"format": "json"}
        if structural.model_year:
            params["modelyear"] = str(structural.model_year)

        try:
            if self._client is not None:
                response = await self._client.get(url, params=params, timeout=self._timeout)
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            self._record_failure()
            return ProviderResult(source=self.key, used=False, error=f"{type(exc).__name__}: {exc}")

        results = payload.get("Results") or []
        if not results:
            self._record_failure()
            return ProviderResult(source=self.key, used=False, error="empty_response")

        self._record_success()
        return ProviderResult(
            source=self.key,
            candidates=self.to_candidates(results[0], structural),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def to_candidates(self, data: dict, structural: StructuralResult) -> list[Candidate]:
        error_codes = {c.strip() for c in str(data.get("ErrorCode", "")).split(",") if c.strip()}
        weight = self._region_weight(structural)
        # 0 = fehlerfrei; 1 = nur Pruefziffer (in Europa normal); alles andere
        # deutet auf eine unvollstaendige Decodierung hin
        if not error_codes or error_codes <= {"0"}:
            base = 0.90
        elif error_codes <= {"0", "1"}:
            base = 0.85
        else:
            base = 0.70
        base *= weight

        out: list[Candidate] = []
        for field, attribute in FIELD_MAP.items():
            cleaned = _clean(data.get(field))
            if cleaned is None:
                continue
            value: object = cleaned
            if attribute in NUMERIC_ATTRIBUTES:
                try:
                    value = int(float(cleaned))
                except ValueError:
                    continue
            elif attribute == Attr.ENGINE_DISPLACEMENT_L:
                try:
                    value = round(float(cleaned), 1)
                except ValueError:
                    continue
            confidence = base
            if attribute == Attr.MODEL_YEAR:
                confidence = min(0.95, base * 1.05)
            out.append(Candidate(attribute, value, self.key, round(min(0.99, confidence), 4)))
        return out
