"""Tests der strukturellen Decodierung (ISO 3779/3780)."""

from __future__ import annotations

import datetime as dt

import pytest
from app.decoder.structural import (
    VinFormatError,
    compute_check_digit,
    decode_structural,
    lookup_country,
    mask_vin,
    normalize_vin,
    resolve_model_year,
    suggest_correction,
    validate_vin,
)

TODAY = dt.date(2026, 1, 1)


# --------------------------------------------------------------------------
# Normalisierung und Validierung
# --------------------------------------------------------------------------


def test_normalize_removes_separators_and_upcases():
    assert normalize_vin(" wvw-zzz 1jz3w386752 ") == "WVWZZZ1JZ3W386752"


@pytest.mark.parametrize(
    ("vin", "code"),
    [
        ("", "vin_empty"),
        ("WVWZZZ1JZ3W38675", "vin_length"),
        ("WVWZZZ1JZ3W3867521", "vin_length"),
        ("WVWZZZ1JZ3W38675I", "vin_invalid_characters"),
        ("WVWZZZ1JZ3W38675O", "vin_invalid_characters"),
        ("WVWZZZ1JZ3W38675Q", "vin_invalid_characters"),
    ],
)
def test_validate_rejects_bad_input(vin, code):
    with pytest.raises(VinFormatError) as excinfo:
        validate_vin(vin)
    assert excinfo.value.code == code


def test_suggestion_for_confusable_characters():
    # I -> 1, O -> 0, Q -> 0; nur als Vorschlag, nie automatisch angewendet
    assert suggest_correction("WVWZZZ1JZ3W3867I2") == "WVWZZZ1JZ3W386712"
    assert suggest_correction("WVWZZZ1JZ3W386752") is None


# --------------------------------------------------------------------------
# Pruefziffer
# --------------------------------------------------------------------------


def test_check_digit_matches_nhtsa_reference_vin():
    assert compute_check_digit("1HGCM82633A004352") == "3"


def test_check_digit_x_case():
    # Rest 10 wird als 'X' geschrieben
    assert compute_check_digit("1M8GDM9AXKP042788") == "X"


def test_check_digit_required_only_where_mandatory():
    european = decode_structural("WVWZZZ1JZ3W386752", today=TODAY)
    assert european.check_digit_required is False
    assert european.check_digit_valid is False  # 'Z' ist ein Fuellzeichen
    assert "check_digit_not_applicable" in european.warnings

    american = decode_structural("1HGCM82633A004352", today=TODAY)
    assert american.check_digit_required is True
    assert american.check_digit_valid is True
    assert "check_digit_mismatch" not in american.warnings


# --------------------------------------------------------------------------
# Land und Region
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wmi", "country", "iso"),
    [
        ("WVW", "Germany", "DE"),
        ("SAL", "United Kingdom", "GB"),
        ("VF1", "France", "FR"),
        ("ZFA", "Italy", "IT"),
        ("TMB", "Czech Republic", "CZ"),
        ("VSS", "Spain", "ES"),
        ("YS3", "Sweden", "SE"),
        ("NM0", "Turkey", "TR"),
        ("NMT", "Turkey", "TR"),
        ("U5Y", "Slovakia", "SK"),
        ("XTA", "Russia", "RU"),
        ("1HG", "United States", "US"),
        ("JHM", "Japan", "JP"),
        ("KNA", "South Korea", "KR"),
        ("LFV", "China", "CN"),
    ],
)
def test_country_ranges(wmi, country, iso):
    assert lookup_country(wmi) == (country, iso)


def test_turkey_counts_as_primary_focus():
    result = decode_structural("NM0LS7E28E1234567", today=TODAY)
    assert result.country_code == "TR"
    assert result.in_primary_focus is True


# --------------------------------------------------------------------------
# Modelljahr
# --------------------------------------------------------------------------


def test_model_year_unambiguous_when_only_one_candidate_is_plausible():
    year, candidates, confidence, warnings = resolve_model_year(
        "3", position_7="1", first_char="W", today=TODAY
    )
    assert (year, candidates) == (2003, [2003])
    assert confidence >= 0.9
    assert warnings == []


def test_model_year_ambiguous_outside_north_america():
    year, candidates, confidence, warnings = resolve_model_year(
        "B", position_7="1", first_char="W", today=TODAY
    )
    assert candidates == [1981, 2011]
    assert year == 2011
    assert confidence < 0.7
    assert "model_year_ambiguous" in warnings


def test_model_year_north_america_uses_position_seven_rule():
    # Buchstabe an Position 7 -> Zyklus ab 2010
    recent, _, confidence, _ = resolve_model_year(
        "B", position_7="A", first_char="1", today=TODAY
    )
    assert recent == 2011
    assert confidence >= 0.9

    # Ziffer an Position 7 -> Zyklus 1980-2009
    older, _, _, _ = resolve_model_year("B", position_7="8", first_char="1", today=TODAY)
    assert older == 1981


def test_invalid_year_code_is_reported():
    result = decode_structural("ZFA31200000123456", today=TODAY)
    assert result.model_year is None
    assert "model_year_code_invalid" in result.warnings


# --------------------------------------------------------------------------
# Struktur
# --------------------------------------------------------------------------


def test_sections_and_lookup_codes():
    result = decode_structural("WVWZZZ1JZ3W386752", today=TODAY)
    assert (result.wmi, result.vds, result.vis) == ("WVW", "ZZZ1JZ", "3W386752")
    assert result.plant_code == "W"
    assert result.wmi_lookup_codes == ["WVW", "WV"]


def test_small_manufacturer_extends_the_wmi():
    # Position 3 == '9' -> Positionen 12-14 gehoeren zur Herstellerkennung
    result = decode_structural("SF9ZZZ1JZ3WABC752", today=TODAY)
    assert result.is_small_manufacturer is True
    assert result.extended_wmi == result.wmi + result.vin[11:14]
    assert result.wmi_lookup_codes[0] == result.extended_wmi


# --------------------------------------------------------------------------
# Datenschutz-Leitplanke
# --------------------------------------------------------------------------


def test_mask_vin_removes_the_serial_number():
    masked = mask_vin("WVWZZZ1JZ3W386752")
    assert masked == "WVWZZZ1JZ3WXXXXXX"
    assert "386752" not in masked
    assert len(masked) == 17


def test_structural_result_keeps_serial_out_of_lookup_codes():
    result = decode_structural("WVWZZZ1JZ3W386752", today=TODAY)
    assert all("386752" not in code for code in result.wmi_lookup_codes)
