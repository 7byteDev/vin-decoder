"""Variante einer Typengenehmigung aus der VIN bestimmen.

Eine Schweizer Typengenehmigung deckt oft mehrere Ausfuehrungen ab. Das
ASTRA gibt Abmessungen und Gewichte dann als Spanne an - der Typenschein
fuehrt aber unter der Ueberschrift "Zuordnung" eine Tabelle nach, die je
Ausfuehrung den konkreten Wert nennt::

    Zuordnung
    05) I023T1        /  I123T1
    44) 3106          /  3216
    52) 2070-2400     /  2090-2441

Zeile 05 listet die Variantencodes, die uebrigen Zeilen die Werte in
derselben Reihenfolge. Welche Ausfuehrung vorliegt, verraet die VIN: das
VIN-Muster der Genehmigung laesst genau die Stelle offen, an der sich die
Varianten unterscheiden.

  Muster    W1K223.33........   -> offene Stelle: Position 7
  Varianten I023T1 / I123T1     -> unterscheiden sich an Index 1: "0"/"1"
  VIN       W1K2231331A079835   -> Position 7 ist "1" -> zweite Variante
                                -> Radstand 3216 mm statt "3106-3216 mm"

Auswertung ueber den Gesamtbestand: 39 326 Genehmigungen fuehren eine
Zuordnungstabelle, bei 3 288 laesst sich die Variante auf diesem Weg
eindeutig bestimmen, bei 1 136 haengt davon der Radstand ab. Wo die
Zuordnung nicht eindeutig ist, bleibt es bei der Spanne - geraten wird
nicht.
"""

from __future__ import annotations

import re

#: Trennzeichen der Zuordnungstabelle. Die Codes selbst koennen einen
#: Schraegstrich enthalten ("FM/00M4?T??21A?T0"), deshalb trennt erst die
#: Kombination aus Leerraum und Schraegstrich.
_SPLIT = re.compile(r"\s{2,}/\s+")
_LINE = re.compile(r"^(\d{2})\)\s*(.+)$")

#: In einer VIN zulaessige Zeichen (I, O und Q sind ausgeschlossen).
VIN_CHARS = frozenset("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")

#: Zeilennummer der Zuordnungstabelle -> Feld der Detailansicht. Die
#: Nummern sind die Positionen des Typenscheins; welche Zeilen eine
#: Genehmigung fuehrt, entscheidet das ASTRA je Fall.
ATTRIBUTION_FIELDS = {
    "19": "top_speed_kmh",
    "37": "seats_total",
    "38": "doors",
    "40": "length_mm",
    "41": "width_mm",
    "42": "height_mm",
    "44": "wheelbase_mm",
    "52": "weight_kg",
    "53": "max_weight_kg",
}

#: Zeile mit den Variantencodes.
VARIANT_LINE = "05"


def parse_attribution(remarks: dict[str, str]) -> dict[str, list[str]]:
    """Die Zuordnungstabelle aus den Bemerkungen lesen.

    ``remarks`` sind die Eintraege des Abschnitts "Bemerkungen, beh.
    Auflagen". Zurueck kommen die Zeilennummern mit ihren Werten je
    Variante.
    """
    table: dict[str, list[str]] = {}
    for value in remarks.values():
        match = _LINE.match((value or "").strip())
        if not match:
            continue
        number, body = match.group(1), match.group(2)
        parts = [p.strip() for p in _SPLIT.split(body) if p.strip()]
        if len(parts) > 1:
            table.setdefault(number, parts)
    return table


def _open_position(pattern: str) -> int | None:
    """Die einzige offene Stelle im beschreibenden Teil (Position 4-9).

    Mehr als eine Luecke laesst sich nicht eindeutig einer Stelle im
    Variantencode zuordnen; dann wird nichts bestimmt.
    """
    holes = [i for i in range(3, min(9, len(pattern))) if pattern[i] == "."]
    return holes[0] if len(holes) == 1 else None


def _distinguishing_chars(codes: list[str]) -> list[str] | None:
    """Die Zeichen, an denen sich die Variantencodes unterscheiden."""
    if len(codes) < 2 or len({len(code) for code in codes}) != 1:
        return None
    positions = [
        i for i in range(len(codes[0])) if len({code[i] for code in codes}) > 1
    ]
    if len(positions) != 1:
        return None
    chars = [code[positions[0]] for code in codes]
    # Nur brauchbar, wenn jedes Zeichen genau eine Variante bezeichnet und
    # in einer VIN ueberhaupt vorkommen kann.
    if len(set(chars)) != len(chars) or not set(chars) <= VIN_CHARS:
        return None
    return chars


def resolve_index(vin: str, pattern: str, codes: list[str]) -> int | None:
    """Index der Variante, die zu dieser VIN gehoert - oder ``None``."""
    position = _open_position(pattern or "")
    chars = _distinguishing_chars(codes)
    if position is None or chars is None or len(vin) <= position:
        return None
    actual = vin[position].upper()
    return chars.index(actual) if actual in chars else None


def _as_range(value: str) -> tuple[int, int | None] | None:
    """Zahlenwert einer Zuordnungszeile.

    Auch die einzelne Ausfuehrung kann noch eine Spanne haben
    ("52) ... / 2090-2441"). Dann bleibt sie erhalten - nur die Spanne
    ueber ALLE Ausfuehrungen faellt weg. Ein Stern kennzeichnet
    Sonderfaelle ("2815/*2900", nur im Anhaengerbetrieb) und wird nicht
    als Obergrenze gewertet.
    """
    text = (value or "").strip()
    span = re.match(r"^(\d+)\s*-\s*(\d+)", text)
    if span:
        return int(span.group(1)), int(span.group(2))
    single = re.search(r"\d+", text)
    return (int(single.group()), None) if single else None


def resolve(vin: str, pattern: str, remarks: dict[str, str]) -> dict[str, object]:
    """Konkrete Werte fuer diese VIN aus der Zuordnungstabelle holen.

    Zurueck kommt ein Woerterbuch mit den Feldern der Detailansicht sowie
    dem Variantencode. Ist die Variante nicht eindeutig, ist es leer.
    """
    table = parse_attribution(remarks)
    codes = table.get(VARIANT_LINE)
    if not codes:
        return {}

    index = resolve_index((vin or "").upper(), pattern, codes)
    if index is None:
        return {}

    resolved: dict[str, object] = {"variant_code": codes[index]}
    upper: dict[str, int] = {}
    for number, field in ATTRIBUTION_FIELDS.items():
        values = table.get(number)
        if not values or len(values) != len(codes):
            continue
        parsed = _as_range(values[index])
        if parsed is None:
            continue
        resolved[field] = parsed[0]
        if parsed[1] is not None and parsed[1] > parsed[0]:
            upper[field] = parsed[1]
    if upper:
        resolved["ranges"] = upper
    return resolved
