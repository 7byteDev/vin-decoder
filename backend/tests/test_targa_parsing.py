"""Tests fuer die Aufbereitung der Schweizer Typengenehmigungsdaten (TARGA)."""

from __future__ import annotations

import pytest

from etl.importers.astra_targa import (
    _int,
    _smallint,
    normalize_drive,
    normalize_fuel,
    parse_transmission,
    split_vin_pattern,
)

# --------------------------------------------------------------------------
# Zahlen
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1969", 1969),
        ("4626", 4626),
        ("105.2", 105),      # Drehmoment mit Dezimalstelle
        ("10,4", 10),
        ("'2", 2),           # fuehrendes Apostroph (Excel-Textmarkierung)
        ("'2+1 / 4+1", 2),   # zwei Tueren, nicht 2141
        ("'2-4", 2),
        ("'1/mit Kabine", 1),
        ("", None),
        ("-", None),
        (None, None),
        ("0", None),
    ],
)
def test_int_takes_the_first_number(raw, expected):
    assert _int(raw) == expected


def test_smallint_rejects_out_of_range_instead_of_crashing():
    """Regression: ein Textwert wurde zu 2141 verklebt und sprengte spaeter int16."""
    assert _smallint("40000") is None
    assert _smallint("255") == 255


# --------------------------------------------------------------------------
# VIN-Muster
# --------------------------------------------------------------------------


def test_vin_pattern_prefix_only():
    pattern, prefix, regex = split_vin_pattern("VF1RJA...........")
    assert prefix == "VF1RJA"
    assert regex is None
    assert pattern == "VF1RJA..........."


def test_vin_pattern_with_inner_wildcards_gets_a_regex():
    result = split_vin_pattern("W0L00002.9.......")
    assert result is not None
    _, prefix, regex = result
    assert prefix == "W0L00002"
    assert regex is not None
    import re

    assert re.match(regex, "W0L00002X9ABCDEFG")
    assert not re.match(regex, "W0L00002XX000000")


def test_vin_pattern_too_short_or_leading_wildcard_is_dropped():
    assert split_vin_pattern("X") is None
    assert split_vin_pattern("..ABC") is None
    assert split_vin_pattern("") is None


# --------------------------------------------------------------------------
# Codes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [("B", "petrol"), ("C", "petrol_direct_injection"), ("D", "diesel"), ("E", "electric")],
)
def test_known_fuel_codes(code, expected):
    assert normalize_fuel(code) == expected


def test_unknown_fuel_code_is_kept_raw():
    assert normalize_fuel("Q") == "Q"
    assert normalize_fuel(None) is None


@pytest.mark.parametrize(
    ("raw", "kind", "gears"),
    [("m6", "manual", 6), ("a8", "automatic", 8), ("s0", "continuous", None), ("", None, None)],
)
def test_transmission(raw, kind, gears):
    assert parse_transmission(raw) == (kind, gears)


def test_drive_type_normalisation():
    assert normalize_drive("Vorderradantrieb") == "front_wheel"
    assert normalize_drive("Allradantrieb") == "all_wheel"
    assert normalize_drive("Hinterradantrieb") == "rear_wheel"
    assert normalize_drive("Sonderkonstruktion") == "Sonderkonstruktion"
