"""Tests der vPIC-Auswertung - ohne Netzzugriff, mit aufgezeichneter Antwort."""

from __future__ import annotations

from app.decoder.structural import decode_structural
from app.decoder.types import Attr
from app.sources.nhtsa import NhtsaProvider

# Gekuerzte, real aufgezeichnete Antwort zu einem VW Golf IV (WVWZZZ1JZ3W386752).
# Bemerkenswert: vPIC kennt Hersteller, Marke, Jahr und Werk - aber kein Modell.
VPIC_GOLF = {
    "ErrorCode": "1,5,14,400",
    "Make": "VOLKSWAGEN",
    "Manufacturer": "VOLKSWAGEN AG",
    "Model": "",
    "ModelYear": "2003",
    "PlantCity": "WOLFSBURG",
    "PlantCountry": "GERMANY",
    "VehicleType": "PASSENGER CAR",
    "BodyClass": "",
    "BedType": "Not Applicable",
    "BusType": "Not Applicable",
    "DisplacementL": "",
}

VPIC_ACCORD = {
    "ErrorCode": "0",
    "Make": "HONDA",
    "Manufacturer": "AMERICAN HONDA MOTOR CO., INC.",
    "Model": "Accord",
    "ModelYear": "2003",
    "BodyClass": "Sedan/Saloon",
    "DisplacementL": "2.4",
    "EngineCylinders": "4",
    "PlantCity": "MARYSVILLE",
    "PlantCountry": "UNITED STATES (USA)",
    "VehicleType": "PASSENGER CAR",
}


def candidates_by_attribute(rows):
    return {row.attribute: row for row in rows}


def test_placeholder_values_are_dropped():
    provider = NhtsaProvider()
    structural = decode_structural("WVWZZZ1JZ3W386752")
    fields = candidates_by_attribute(provider.to_candidates(VPIC_GOLF, structural))

    assert Attr.MODEL not in fields          # leer
    assert Attr.BODY_CLASS not in fields     # leer
    assert fields[Attr.MAKE].value == "VOLKSWAGEN"
    assert fields[Attr.MODEL_YEAR].value == 2003
    assert isinstance(fields[Attr.MODEL_YEAR].value, int)


def test_european_results_are_weighted_lower_than_us_results():
    provider = NhtsaProvider()
    eu = candidates_by_attribute(
        provider.to_candidates(VPIC_GOLF, decode_structural("WVWZZZ1JZ3W386752"))
    )
    us = candidates_by_attribute(
        provider.to_candidates(VPIC_ACCORD, decode_structural("1HGCM82633A004352"))
    )
    assert us[Attr.MAKE].confidence > eu[Attr.MAKE].confidence


def test_numeric_fields_are_typed():
    provider = NhtsaProvider()
    fields = candidates_by_attribute(
        provider.to_candidates(VPIC_ACCORD, decode_structural("1HGCM82633A004352"))
    )
    assert fields[Attr.ENGINE_DISPLACEMENT_L].value == 2.4
    assert fields[Attr.ENGINE_CYLINDERS].value == 4


def test_error_codes_reduce_confidence():
    provider = NhtsaProvider()
    structural = decode_structural("1HGCM82633A004352")
    clean = candidates_by_attribute(provider.to_candidates(VPIC_ACCORD, structural))
    dirty = candidates_by_attribute(
        provider.to_candidates({**VPIC_ACCORD, "ErrorCode": "5,14"}, structural)
    )
    assert clean[Attr.MAKE].confidence > dirty[Attr.MAKE].confidence


async def test_network_failure_is_reported_not_raised(monkeypatch):
    provider = NhtsaProvider(base_url="http://127.0.0.1:9", timeout=0.05)
    result = await provider.fetch(decode_structural("WVWZZZ1JZ3W386752"))
    assert result.used is False
    assert result.error
    assert result.candidates == []


async def test_circuit_opens_after_repeated_failures():
    """Nach mehreren Fehlern wird die Quelle uebersprungen statt erneut befragt."""
    provider = NhtsaProvider(base_url="http://127.0.0.1:9", timeout=0.05, failure_threshold=3)
    structural = decode_structural("WVWZZZ1JZ3W386752")

    for _ in range(3):
        assert (await provider.fetch(structural)).used is False
    assert provider.circuit_open is True

    result = await provider.fetch(structural)
    assert result.error == "circuit_open"


async def test_circuit_stays_closed_while_the_source_answers():
    provider = NhtsaProvider(failure_threshold=2)
    assert provider.circuit_open is False
    provider._record_success()
    assert provider.circuit_open is False
