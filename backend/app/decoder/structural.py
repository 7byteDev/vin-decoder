"""Strukturelle VIN-Decodierung nach ISO 3779 / ISO 3780.

Diese Schicht ist bewusst frei von Datenbank- und Netzwerkzugriffen: sie
liefert alles, was sich allein aus dem Aufbau der VIN ergibt, und ist damit
deterministisch, offline lauffaehig und vollstaendig testbar.

Aufbau einer VIN (17 Zeichen):

    Position  1- 3  WMI  - World Manufacturer Identifier
    Position  4- 9  VDS  - Vehicle Descriptor Section (herstellerspezifisch!)
    Position     9  Pruefziffer (in NA/China verbindlich, in Europa oft Fuellzeichen)
    Position 10-17  VIS  - Vehicle Identifier Section
    Position    10  Modelljahr-Code
    Position    11  Werkscode (herstellerspezifisch)
    Position 12-17  Seriennummer (bei Kleinserien enthalten 12-14 die WMI-Erweiterung)
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

from .constants import (
    CHECK_DIGIT_MANDATORY_FIRST_CHARS,
    CHECK_DIGIT_WEIGHTS,
    CONFUSABLES,
    COUNTRY_RANGES,
    MODEL_YEAR_CODES,
    PRIMARY_FOCUS_CODES,
    REGIONS,
    TRANSLITERATION,
    VIN_ALPHABET,
    VIN_LENGTH,
    WMI_ORDER_INDEX,
)

__all__ = [
    "StructuralResult",
    "VinFormatError",
    "compute_check_digit",
    "decode_structural",
    "mask_vin",
    "normalize_vin",
    "validate_vin",
]


class VinFormatError(ValueError):
    """Die Eingabe ist keine formal gueltige VIN."""

    def __init__(self, code: str, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


@dataclass(slots=True)
class StructuralResult:
    """Ergebnis der rein strukturellen Decodierung."""

    vin: str
    wmi: str
    vds: str
    vis: str
    region_code: str | None = None
    region_name: str | None = None
    country: str | None = None
    country_code: str | None = None
    in_primary_focus: bool = False
    extended_wmi: str | None = None
    is_small_manufacturer: bool = False
    check_digit: str | None = None
    check_digit_expected: str | None = None
    check_digit_valid: bool | None = None
    check_digit_required: bool = False
    model_year_code: str | None = None
    model_year: int | None = None
    model_year_candidates: list[int] = field(default_factory=list)
    model_year_confidence: float = 0.0
    plant_code: str | None = None
    serial: str | None = None
    sequential_number: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def wmi_lookup_codes(self) -> list[str]:
        """WMI-Codes fuer den DB-Abgleich, spezifischster zuerst.

        Das 2-stellige Praefix ist bewusst dabei: mehrere Quellen fuehren
        Hersteller nur auf dieser Ebene (z. B. "1N" fuer Nissan USA).
        """
        codes = []
        if self.extended_wmi:
            codes.append(self.extended_wmi)
        codes.append(self.wmi)
        codes.append(self.wmi[:2])
        return codes


# ---------------------------------------------------------------------------
# Normalisierung & Validierung
# ---------------------------------------------------------------------------


def normalize_vin(raw: str) -> str:
    """Grossschreiben, Trenner entfernen. Keine Zeichenkorrektur."""
    if raw is None:
        return ""
    return "".join(ch for ch in raw.strip().upper() if not ch.isspace() and ch not in "-_.")


def suggest_correction(raw: str) -> str | None:
    """Vorschlag fuer typische Tippfehler (I->1, O->0, Q->0), nie automatisch."""
    normalized = normalize_vin(raw)
    if len(normalized) != VIN_LENGTH:
        return None
    if not any(ch in CONFUSABLES for ch in normalized):
        return None
    fixed = "".join(CONFUSABLES.get(ch, ch) for ch in normalized)
    return fixed if all(ch in VIN_ALPHABET for ch in fixed) else None


def validate_vin(vin: str) -> str:
    """Formale Pruefung. Wirft ``VinFormatError`` mit maschinenlesbarem Code."""
    normalized = normalize_vin(vin)
    if not normalized:
        raise VinFormatError("vin_empty", "VIN is empty")
    if len(normalized) != VIN_LENGTH:
        raise VinFormatError(
            "vin_length",
            f"VIN must be {VIN_LENGTH} characters, got {len(normalized)}",
            detail={"length": len(normalized)},
        )
    invalid = sorted({ch for ch in normalized if ch not in VIN_ALPHABET})
    if invalid:
        raise VinFormatError(
            "vin_invalid_characters",
            f"VIN contains invalid characters: {', '.join(invalid)}",
            detail={"characters": invalid, "suggestion": suggest_correction(vin)},
        )
    return normalized


# ---------------------------------------------------------------------------
# Pruefziffer
# ---------------------------------------------------------------------------


def compute_check_digit(vin: str) -> str:
    """Pruefziffer nach 49 CFR 565 berechnen (Position 9)."""
    total = sum(TRANSLITERATION[ch] * w for ch, w in zip(vin, CHECK_DIGIT_WEIGHTS, strict=True))
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


# ---------------------------------------------------------------------------
# Land / Region
# ---------------------------------------------------------------------------


def _wmi_key(two_chars: str) -> int | None:
    try:
        return WMI_ORDER_INDEX[two_chars[0]] * 100 + WMI_ORDER_INDEX[two_chars[1]]
    except (KeyError, IndexError):
        return None


def lookup_region(first_char: str) -> tuple[str | None, str | None]:
    for start, end, code, name in REGIONS:
        if start <= first_char <= end:
            return code, name
    return None, None


def lookup_country(wmi: str) -> tuple[str | None, str | None]:
    """Land aus den ersten beiden WMI-Zeichen nach ISO 3780."""
    key = _wmi_key(wmi[:2])
    if key is None:
        return None, None
    for start, end, country, iso in COUNTRY_RANGES:
        start_key, end_key = _wmi_key(start), _wmi_key(end)
        if start_key is None or end_key is None:
            continue
        if start_key <= key <= end_key:
            return country, iso
    return None, None


# ---------------------------------------------------------------------------
# Modelljahr
# ---------------------------------------------------------------------------


def resolve_model_year(
    code: str,
    *,
    position_7: str,
    first_char: str,
    today: _dt.date | None = None,
) -> tuple[int | None, list[int], float, list[str]]:
    """Modelljahr aus Position 10 aufloesen.

    Der Code wiederholt sich alle 30 Jahre, ist also nie eindeutig. Zur
    Aufloesung dienen zwei Regeln:

    * Nordamerika (Position 1 = 1-5): ist Position 7 ein Buchstabe, gehoert
      das Fahrzeug in den Zyklus ab 2010, sonst in 1980-2009 (49 CFR 565).
    * Sonst: der juengste Kandidat, der nicht in der Zukunft liegt
      (Modelljahre werden bis zu einem Jahr im Voraus vergeben).
    """
    warnings: list[str] = []
    candidates = MODEL_YEAR_CODES.get(code)
    if not candidates:
        return None, [], 0.0, ["model_year_code_invalid"]

    today = today or _dt.date.today()
    max_year = today.year + 1
    plausible = [y for y in candidates if 1980 <= y <= max_year]
    if not plausible:
        return None, list(candidates), 0.0, ["model_year_out_of_range"]

    if first_char in "12345" and len(plausible) > 1:
        if position_7.isalpha():
            selected = [y for y in plausible if y >= 2010]
        else:
            selected = [y for y in plausible if y < 2010]
        if selected:
            return selected[-1], plausible, 0.95, warnings
        warnings.append("model_year_position7_rule_inconclusive")

    if len(plausible) == 1:
        return plausible[0], plausible, 0.9, warnings

    warnings.append("model_year_ambiguous")
    return plausible[-1], plausible, 0.6, warnings


# ---------------------------------------------------------------------------
# Maskierung (Datenschutz-Leitplanke)
# ---------------------------------------------------------------------------


def mask_vin(vin: str) -> str:
    """VIN auf den technischen Teil kuerzen (Position 1-11 + Maske).

    Die Seriennummer identifiziert ein einzelnes Fahrzeug und wird deshalb
    nirgends gespeichert - weder im Log noch in ``vehicles_reference``.
    """
    normalized = normalize_vin(vin)
    if len(normalized) < VIN_LENGTH:
        return (normalized[:11] or "?").ljust(11, "?") + "XXXXXX"
    return normalized[:11] + "XXXXXX"


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------


def decode_structural(vin: str, *, today: _dt.date | None = None) -> StructuralResult:
    """Vollstaendige strukturelle Decodierung einer formal gueltigen VIN."""
    normalized = validate_vin(vin)
    warnings: list[str] = []

    wmi = normalized[0:3]
    vds = normalized[3:9]
    vis = normalized[9:17]

    region_code, region_name = lookup_region(normalized[0])
    country, country_code = lookup_country(wmi)
    if country is None:
        warnings.append("country_range_unassigned")

    # Kleinserienhersteller (< 1000 Fahrzeuge/Jahr): WMI wird durch die
    # Positionen 12-14 vervollstaendigt.
    is_small = wmi[2] == "9"
    extended = wmi + normalized[11:14] if is_small else None

    check_digit = normalized[8]
    expected = compute_check_digit(normalized)
    required = normalized[0] in CHECK_DIGIT_MANDATORY_FIRST_CHARS
    valid = check_digit == expected
    if not valid:
        warnings.append("check_digit_mismatch" if required else "check_digit_not_applicable")

    year_code = normalized[9]
    model_year, candidates, year_conf, year_warnings = resolve_model_year(
        year_code, position_7=normalized[6], first_char=normalized[0], today=today
    )
    warnings.extend(year_warnings)

    return StructuralResult(
        vin=normalized,
        wmi=wmi,
        vds=vds,
        vis=vis,
        region_code=region_code,
        region_name=region_name,
        country=country,
        country_code=country_code,
        in_primary_focus=country_code in PRIMARY_FOCUS_CODES if country_code else False,
        extended_wmi=extended,
        is_small_manufacturer=is_small,
        check_digit=check_digit,
        check_digit_expected=expected,
        check_digit_valid=valid,
        check_digit_required=required,
        model_year_code=year_code,
        model_year=model_year,
        model_year_candidates=candidates,
        model_year_confidence=year_conf,
        plant_code=normalized[10],
        serial=normalized[11:17],
        sequential_number=normalized[14:17] if is_small else normalized[11:17],
        warnings=warnings,
    )
