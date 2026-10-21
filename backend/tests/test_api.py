"""Tests der HTTP-Schnittstelle (ohne Datenbank, ohne Live-Abfrage)."""

from __future__ import annotations

VIN_DE = "WVWZZZ1JZ3W386752"


def test_health_reports_structural_only_mode(client):
    body = client.get("/health").json()
    assert body["mode"] == "structural_only"
    assert body["database"] is False


def test_decode_returns_structure_and_fields(client):
    body = client.get(f"/api/v1/decode/{VIN_DE}").json()
    assert body["structure"]["wmi"] == "WVW"
    assert body["structure"]["vis_masked"] == "3WXXXXXX"
    assert body["structure"]["country_code"] == "DE"
    assert body["structure"]["model_year"] == 2003
    assert body["fields"]["country"]["value"] == "Germany"
    assert body["fields"]["country"]["sources"] == ["structural"]
    assert 0.0 <= body["confidence"] <= 1.0


def test_response_never_contains_the_full_vin(client):
    raw = client.get(f"/api/v1/decode/{VIN_DE}").text
    assert VIN_DE not in raw
    assert "WVWZZZ1JZ3WXXXXXX" in raw
    # Die Seriennummer taucht nirgends auf
    assert "386752" not in raw


def test_status_is_partial_without_model_data(client):
    body = client.get(f"/api/v1/decode/{VIN_DE}").json()
    assert body["status"] == "partial"
    assert "manufacturer_unknown" in body["warnings"]


def test_invalid_vin_returns_422_with_machine_readable_code(client):
    response = client.get("/api/v1/decode/WVWZZZ1JZ3W38675")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "vin_length"


def test_invalid_characters_include_a_suggestion(client):
    response = client.get("/api/v1/decode/WVWZZZ1JZ3W3867I2")
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "vin_invalid_characters"
    assert error["detail"]["suggestion"] == "WVWZZZ1JZ3W386712"


def test_post_and_get_agree(client):
    from_get = client.get(f"/api/v1/decode/{VIN_DE}").json()
    from_post = client.post("/api/v1/decode", json={"vin": VIN_DE, "lang": "tr"}).json()
    assert from_get["fields"]["country"] == from_post["fields"]["country"]
    assert from_get["structure"] == from_post["structure"]


def test_lowercase_and_spaced_input_is_accepted(client):
    body = client.post("/api/v1/decode", json={"vin": " wvwzzz1jz3w386752 "}).json()
    assert body["structure"]["wmi"] == "WVW"


def test_attributes_endpoint_lists_translation_keys(client):
    attributes = client.get("/api/v1/attributes").json()["attributes"]
    assert "make" in attributes
    assert "model_year" in attributes
    assert "plant_city" in attributes


def test_stats_without_database(client):
    body = client.get("/api/v1/stats").json()
    assert body["database"] is False
    assert body["wmi_codes"] == 0


def test_openapi_is_generated(client):
    schema = client.get("/openapi.json").json()
    assert "/api/v1/decode/{vin}" in schema["paths"]
