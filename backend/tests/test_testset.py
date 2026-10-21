"""Regressionstest gegen das Test-VIN-Set aus qa/testset.json.

Geprueft wird hier nur, was ohne Datenbank und ohne Netz entscheidbar ist:
Land und Modelljahr. Marke und Modell werden in Phase 4 gegen die befuellte
Datenbank gemessen (scripts/accuracy_report.py).
"""

from __future__ import annotations

import json

import pytest
from app.decoder.structural import decode_structural


def load_cases(project_root):
    path = project_root / "qa" / "testset.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("qa/testset.json fehlt - 'python etl/build_testset.py' ausfuehren")
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def test_testset_is_present_and_sane(project_root):
    cases = load_cases(project_root)
    assert len(cases) >= 25
    assert len({c["vin"] for c in cases}) == len(cases)
    focus_countries = {"DE", "FR", "IT", "ES", "CZ", "SK", "GB", "SE", "TR"}
    focus = [c for c in cases if c["expect"]["country_code"] in focus_countries]
    assert len(focus) / len(cases) > 0.6, "Testset soll den EU/TR-Schwerpunkt abbilden"


def test_every_case_decodes_structurally(project_root):
    for case in load_cases(project_root):
        result = decode_structural(case["vin"])
        assert result.wmi == case["structural"]["wmi"]


def test_country_matches_expectation(project_root):
    mismatches = []
    for case in load_cases(project_root):
        result = decode_structural(case["vin"])
        if result.country_code != case["expect"]["country_code"]:
            mismatches.append((case["vin"], case["expect"]["country_code"], result.country_code))
    assert not mismatches, f"Landzuordnung weicht ab: {mismatches}"


def test_model_year_matches_expectation_where_unambiguous(project_root):
    mismatches = []
    for case in load_cases(project_root):
        expected = case["expect"]["model_year"]
        if expected is None:
            continue
        result = decode_structural(case["vin"])
        if result.model_year != expected:
            mismatches.append((case["vin"], expected, result.model_year))
    assert not mismatches, f"Modelljahr weicht ab: {mismatches}"


def test_ambiguous_cases_expose_all_candidates(project_root):
    ambiguous = [c for c in load_cases(project_root) if c["expect"]["model_year"] is None]
    assert ambiguous, "Das Testset soll mindestens einen mehrdeutigen Jahrescode enthalten"
    for case in ambiguous:
        result = decode_structural(case["vin"])
        assert len(result.model_year_candidates) > 1
        assert "model_year_ambiguous" in result.warnings


def test_vpic_gap_is_documented(project_root):
    """Die Luecke bei europaeischen Modellen ist der Grund fuer die eigene DB."""
    cases = load_cases(project_root)
    without_model = [c for c in cases if not c["vpic_knows_model"]]
    assert len(without_model) > len(cases) / 3
