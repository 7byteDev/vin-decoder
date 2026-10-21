"""Tests der Aufloesungskette: Merge, Konfidenz, Widersprueche, Live-Fallback."""

from __future__ import annotations

import pytest
from app.decoder.engine import decode, merge_candidates, overall_confidence
from app.decoder.structural import decode_structural
from app.decoder.types import Attr, Candidate, ProviderResult

VIN_DE = "WVWZZZ1JZ3W386752"


class FakeProvider:
    """Provider-Attrappe mit fester Antwort."""

    def __init__(self, key: str, candidates: list[Candidate], error: str | None = None) -> None:
        self.key = key
        self._candidates = candidates
        self._error = error
        self.calls = 0

    async def fetch(self, structural):
        self.calls += 1
        return ProviderResult(source=self.key, candidates=self._candidates, error=self._error)


def c(attribute, value, source, confidence):
    return Candidate(attribute, value, source, confidence)


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------


def test_agreeing_sources_increase_confidence():
    merged = merge_candidates(
        [
            c(Attr.MAKE, "Volkswagen", "a", 0.7),
            c(Attr.MAKE, "volkswagen ", "b", 0.7),
        ]
    )
    field = merged[Attr.MAKE]
    assert field.value == "Volkswagen"
    assert field.confidence > 0.7  # Noisy-OR: zwei unabhaengige Quellen
    assert field.sources == ["a", "b"]
    assert field.conflict is False


def test_same_source_twice_does_not_stack():
    single = merge_candidates([c(Attr.MAKE, "Volkswagen", "a", 0.7)])[Attr.MAKE].confidence
    twice = merge_candidates(
        [c(Attr.MAKE, "Volkswagen", "a", 0.7), c(Attr.MAKE, "Volkswagen", "a", 0.7)]
    )[Attr.MAKE].confidence
    assert single == twice


def test_conflicting_sources_are_flagged_not_hidden():
    merged = merge_candidates(
        [
            c(Attr.MODEL, "Golf", "a", 0.8),
            c(Attr.MODEL, "Bora", "b", 0.75),
        ]
    )
    field = merged[Attr.MODEL]
    assert field.value == "Golf"
    assert field.conflict is True
    assert field.confidence < 0.8  # Widerspruch mindert die Konfidenz
    assert field.alternatives[0]["value"] == "Bora"
    assert field.alternatives[0]["sources"] == ["b"]


def test_clear_winner_is_not_flagged_as_conflict():
    merged = merge_candidates(
        [c(Attr.MODEL, "Golf", "a", 0.9), c(Attr.MODEL, "Bora", "b", 0.2)]
    )
    assert merged[Attr.MODEL].conflict is False


def test_empty_values_are_ignored():
    merged = merge_candidates(
        [c(Attr.MODEL, None, "a", 0.9), c(Attr.MODEL, "  ", "b", 0.9)]
    )
    assert Attr.MODEL not in merged


def test_numeric_values_compare_across_types():
    merged = merge_candidates(
        [c(Attr.MODEL_YEAR, 2003, "a", 0.8), c(Attr.MODEL_YEAR, 2003.0, "b", 0.8)]
    )
    assert len(merged[Attr.MODEL_YEAR].sources) == 2
    assert merged[Attr.MODEL_YEAR].conflict is False


# --------------------------------------------------------------------------
# Gesamtkonfidenz
# --------------------------------------------------------------------------


def test_more_coverage_yields_higher_overall_confidence():
    structural = decode_structural(VIN_DE)
    few = merge_candidates([c(Attr.COUNTRY, "Germany", "s", 0.95)])
    many = merge_candidates(
        [
            c(Attr.COUNTRY, "Germany", "s", 0.95),
            c(Attr.MANUFACTURER, "Volkswagen AG", "a", 0.9),
            c(Attr.MAKE, "Volkswagen", "a", 0.9),
            c(Attr.MODEL, "Golf", "a", 0.9),
            c(Attr.MODEL_YEAR, 2003, "s", 0.9),
            c(Attr.VEHICLE_TYPE, "Passenger Car", "a", 0.9),
        ]
    )
    assert overall_confidence(many, structural) > overall_confidence(few, structural)


def test_failed_mandatory_check_digit_lowers_confidence():
    valid = decode_structural("1HGCM82633A004352")
    broken = decode_structural("1HGCM82634A004352")  # Pruefziffer absichtlich falsch
    assert broken.check_digit_valid is False
    fields = merge_candidates(
        [c(Attr.MAKE, "Honda", "a", 0.9), c(Attr.MODEL_YEAR, 2003, "s", 0.9)]
    )
    assert overall_confidence(fields, broken) < overall_confidence(fields, valid)


def test_european_filler_check_digit_does_not_lower_confidence():
    structural = decode_structural(VIN_DE)
    assert structural.check_digit_valid is False
    assert structural.check_digit_required is False
    fields = merge_candidates([c(Attr.MAKE, "Volkswagen", "a", 0.9)])
    assert overall_confidence(fields, structural) > 0.0


# --------------------------------------------------------------------------
# Orchestrierung
# --------------------------------------------------------------------------


async def test_structural_only_run_needs_no_providers():
    outcome = await decode(VIN_DE, db_providers=[], live_providers=[], allow_live=False)
    assert outcome.fields[Attr.COUNTRY].value == "Germany"
    assert outcome.sources_used == ["structural"]
    assert "manufacturer_unknown" in outcome.warnings


async def test_live_provider_is_only_used_when_the_database_leaves_gaps():
    complete = [
        c(Attr.MANUFACTURER, "Volkswagen AG", "vindb", 0.9),
        c(Attr.MAKE, "Volkswagen", "vindb", 0.9),
        c(Attr.MODEL, "Golf", "vindb", 0.9),
    ]
    live = FakeProvider("nhtsa_vpic", [c(Attr.MODEL, "Golf", "nhtsa_vpic", 0.5)])

    await decode(VIN_DE, db_providers=[FakeProvider("vindb", complete)], live_providers=[live])
    assert live.calls == 0

    live.calls = 0
    await decode(VIN_DE, db_providers=[FakeProvider("vindb", [])], live_providers=[live])
    assert live.calls == 1


async def test_provider_failure_does_not_break_the_decode():
    class Broken:
        key = "broken"

        async def fetch(self, structural):
            raise RuntimeError("boom")

    outcome = await decode(VIN_DE, db_providers=[Broken()], live_providers=[], allow_live=False)
    assert outcome.provider_errors["broken"] == "boom"
    assert outcome.fields[Attr.COUNTRY].value == "Germany"


async def test_masked_vin_never_contains_the_serial():
    outcome = await decode(VIN_DE, db_providers=[], live_providers=[], allow_live=False)
    assert outcome.vin_masked.endswith("XXXXXX")
    assert "386752" not in outcome.vin_masked


@pytest.mark.parametrize("vin", ["", "ABC", "WVWZZZ1JZ3W38675I"])
async def test_invalid_input_raises(vin):
    from app.decoder.structural import VinFormatError

    with pytest.raises(VinFormatError):
        await decode(vin, db_providers=[], live_providers=[], allow_live=False)
