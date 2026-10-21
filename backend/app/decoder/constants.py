"""Konstanten der strukturellen VIN-Decodierung (ISO 3779 / ISO 3780).

Alles in diesem Modul ist deterministisch aus den Normen ableitbar und
haengt an keiner externen Datenquelle. Entsprechend wird es in der
Quellen-Registry als Quelle ``structural`` gefuehrt.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Zeichenvorrat
# ---------------------------------------------------------------------------

#: In einer VIN zulaessige Zeichen. I, O und Q sind ausgeschlossen, weil sie
#: mit 1, 0 und 0 verwechselt werden koennen.
VIN_ALPHABET = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"

#: Haeufige Fehleingaben -> Korrektur (nur als Vorschlag, nie still angewendet).
CONFUSABLES = {"I": "1", "O": "0", "Q": "0"}

#: Sortierreihenfolge der WMI-Zeichen fuer Bereichsvergleiche ("SA-SM").
#: Buchstaben zuerst, danach 1-9 und zuletzt 0 - so werden Bereiche wie
#: "JA-J0" (= ganz Japan) oder "XX-X2" (= Luxemburg) korrekt abgedeckt.
WMI_ORDER = "ABCDEFGHJKLMNPRSTUVWXYZ1234567890"
WMI_ORDER_INDEX = {c: i for i, c in enumerate(WMI_ORDER)}

VIN_LENGTH = 17

# ---------------------------------------------------------------------------
# Pruefziffer (Position 9)
# ---------------------------------------------------------------------------

TRANSLITERATION = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
    **{str(d): d for d in range(10)},
}

CHECK_DIGIT_WEIGHTS = (8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2)

#: Regionen, in denen die Pruefziffer verbindlich ist. In Europa ist
#: Position 9 haeufig ein Fuellzeichen (z. B. "WVWZZZ..."), eine
#: fehlschlagende Pruefziffer ist dort daher kein Fehler.
CHECK_DIGIT_MANDATORY_FIRST_CHARS = set("12345L")

# ---------------------------------------------------------------------------
# Modelljahr (Position 10) - 30-Jahres-Zyklus
# ---------------------------------------------------------------------------

_YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"  # 30 Zeichen, Start 1980

MODEL_YEAR_CODES: dict[str, tuple[int, ...]] = {
    code: (1980 + i, 2010 + i, 2040 + i) for i, code in enumerate(_YEAR_CODES)
}

# ---------------------------------------------------------------------------
# Region (Position 1)
# ---------------------------------------------------------------------------

REGIONS = (
    ("A", "H", "AF", "Africa"),
    ("J", "R", "AS", "Asia"),
    ("S", "Z", "EU", "Europe"),
    ("1", "5", "NA", "North America"),
    ("6", "7", "OC", "Oceania"),
    ("8", "9", "SA", "South America"),
)

# ---------------------------------------------------------------------------
# Laenderbereiche nach ISO 3780 (Position 1-2)
# Format: (bereich_start, bereich_ende, laendername, iso3166-alpha2)
# ---------------------------------------------------------------------------

COUNTRY_RANGES: tuple[tuple[str, str, str, str | None], ...] = (
    # --- Afrika -----------------------------------------------------------
    ("AA", "AH", "South Africa", "ZA"),
    ("AJ", "AN", "Ivory Coast", "CI"),
    ("BA", "BE", "Angola", "AO"),
    ("BF", "BK", "Kenya", "KE"),
    ("BL", "BR", "Tanzania", "TZ"),
    ("CA", "CE", "Benin", "BJ"),
    ("CF", "CK", "Madagascar", "MG"),
    ("CL", "CR", "Tunisia", "TN"),
    ("DA", "DE", "Egypt", "EG"),
    ("DF", "DK", "Morocco", "MA"),
    ("DL", "DR", "Zambia", "ZM"),
    ("EA", "EE", "Ethiopia", "ET"),
    ("EF", "EK", "Mozambique", "MZ"),
    ("FA", "FE", "Ghana", "GH"),
    ("FF", "FK", "Nigeria", "NG"),
    # --- Asien ------------------------------------------------------------
    ("JA", "J0", "Japan", "JP"),
    ("KA", "KE", "Sri Lanka", "LK"),
    ("KF", "KK", "Israel", "IL"),
    ("KL", "KR", "South Korea", "KR"),
    ("KS", "K0", "Kazakhstan", "KZ"),
    ("LA", "L0", "China", "CN"),
    ("MA", "ME", "India", "IN"),
    ("MF", "MK", "Indonesia", "ID"),
    ("ML", "MR", "Thailand", "TH"),
    ("MS", "M0", "Myanmar", "MM"),
    ("NA", "NE", "Iran", "IR"),
    ("NF", "NK", "Pakistan", "PK"),
    ("NL", "NR", "Turkey", "TR"),
    ("PA", "PE", "Philippines", "PH"),
    ("PF", "PK", "Singapore", "SG"),
    ("PL", "PR", "Malaysia", "MY"),
    ("RA", "RE", "United Arab Emirates", "AE"),
    ("RF", "RK", "Taiwan", "TW"),
    ("RL", "RR", "Vietnam", "VN"),
    ("RS", "R0", "Saudi Arabia", "SA"),
    # --- Europa -----------------------------------------------------------
    ("SA", "SM", "United Kingdom", "GB"),
    ("SN", "ST", "Germany", "DE"),
    ("SU", "SZ", "Poland", "PL"),
    ("S1", "S4", "Latvia", "LV"),
    ("TA", "TH", "Switzerland", "CH"),
    ("TJ", "TP", "Czech Republic", "CZ"),
    ("TR", "TV", "Hungary", "HU"),
    ("TW", "T1", "Portugal", "PT"),
    ("UH", "UM", "Denmark", "DK"),
    ("UN", "UT", "Ireland", "IE"),
    ("UU", "UZ", "Romania", "RO"),
    ("U5", "U7", "Slovakia", "SK"),
    ("VA", "VE", "Austria", "AT"),
    ("VF", "VR", "France", "FR"),
    ("VS", "VW", "Spain", "ES"),
    ("VX", "V2", "Serbia", "RS"),
    ("V3", "V5", "Croatia", "HR"),
    ("V6", "V0", "Estonia", "EE"),
    ("WA", "W0", "Germany", "DE"),
    ("XA", "XE", "Bulgaria", "BG"),
    ("XF", "XK", "Greece", "GR"),
    ("XL", "XR", "Netherlands", "NL"),
    ("XS", "XW", "Russia", "RU"),
    ("XX", "X2", "Luxembourg", "LU"),
    ("X3", "X0", "Russia", "RU"),
    ("YA", "YE", "Belgium", "BE"),
    ("YF", "YK", "Finland", "FI"),
    ("YL", "YR", "Malta", "MT"),
    ("YS", "YW", "Sweden", "SE"),
    ("YX", "Y2", "Norway", "NO"),
    ("Y3", "Y5", "Belarus", "BY"),
    ("Y6", "Y0", "Ukraine", "UA"),
    ("ZA", "ZR", "Italy", "IT"),
    ("ZX", "Z2", "Slovenia", "SI"),
    ("Z3", "Z5", "Lithuania", "LT"),
    ("Z6", "Z0", "Russia", "RU"),
    # --- Nordamerika ------------------------------------------------------
    ("1A", "10", "United States", "US"),
    ("2A", "20", "Canada", "CA"),
    ("3A", "3W", "Mexico", "MX"),
    ("3X", "37", "Costa Rica", "CR"),
    ("38", "30", "Cayman Islands", "KY"),
    ("4A", "40", "United States", "US"),
    ("5A", "50", "United States", "US"),
    # --- Ozeanien ---------------------------------------------------------
    ("6A", "6W", "Australia", "AU"),
    ("7A", "7E", "New Zealand", "NZ"),
    # --- Suedamerika ------------------------------------------------------
    ("8A", "8E", "Argentina", "AR"),
    ("8F", "8K", "Chile", "CL"),
    ("8L", "8R", "Ecuador", "EC"),
    ("8S", "8W", "Peru", "PE"),
    ("8X", "82", "Venezuela", "VE"),
    ("9A", "9E", "Brazil", "BR"),
    ("9F", "9K", "Colombia", "CO"),
    ("9L", "9R", "Paraguay", "PY"),
    ("9S", "9W", "Uruguay", "UY"),
    ("9X", "92", "Trinidad and Tobago", "TT"),
    ("93", "99", "Brazil", "BR"),
)

#: Laender im primaeren Marktfokus des Projekts (Europa inkl. Tuerkei).
EU_COUNTRY_CODES = frozenset(
    {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
        "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
        "SI", "ES", "SE",
    }
)
EUROPE_EXTENDED_CODES = EU_COUNTRY_CODES | {"GB", "CH", "NO", "RS", "TR", "UA", "BY", "RU"}
PRIMARY_FOCUS_CODES = EU_COUNTRY_CODES | {"GB", "CH", "NO", "RS", "TR"}
