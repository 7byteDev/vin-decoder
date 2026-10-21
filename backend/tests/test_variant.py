"""Zuordnung der Variante aus der VIN.

Die Beispiele stammen aus dem Bestand: Mercedes-Benz S 400 d 4m (kurz
gegen lang) und Citroen Jumpy (zwei Radstaende). Beide Faelle wurden am
Datensatz geprueft, bevor die Regel entstand.
"""

from app.decoder.variant import parse_attribution, resolve, resolve_index

# Genehmigung 1MJ827, Muster W1K223.33........
MERCEDES = {
    "Bemerkungen Z14": "Zuordnung",
    "Bemerkungen Z15": "05) I023T1                                   /  I123T1",
    "Bemerkungen Z16": "44) 3106                                     /  3216",
    "Bemerkungen Z17": "52) 2070-2400                                /  2090-2441",
    "Bemerkungen Z18": "53) 2770/*2855                               /  2815/*2900",
}
MERCEDES_PATTERN = "W1K223.33........"


def test_zuordnungstabelle_wird_gelesen():
    table = parse_attribution(MERCEDES)
    assert table["05"] == ["I023T1", "I123T1"]
    assert table["44"] == ["3106", "3216"]


def test_lange_ausfuehrung_wird_erkannt():
    # Position 7 der VIN ist "1" -> zweite Variante
    result = resolve("W1K2231331A079835", MERCEDES_PATTERN, MERCEDES)
    assert result["variant_code"] == "I123T1"
    assert result["wheelbase_mm"] == 3216
    assert result["weight_kg"] == 2090
    assert result["max_weight_kg"] == 2815
    # Das Leergewicht dieser Ausfuehrung ist selbst eine Spanne
    assert result["ranges"]["weight_kg"] == 2441
    # Der Stern-Wert (nur im Anhaengerbetrieb) ist keine Obergrenze
    assert "max_weight_kg" not in result["ranges"]


def test_kurze_ausfuehrung_wird_erkannt():
    # dieselbe Genehmigung, Position 7 ist "0"
    result = resolve("W1K2230331A079835", MERCEDES_PATTERN, MERCEDES)
    assert result["variant_code"] == "I023T1"
    assert result["wheelbase_mm"] == 3106
    assert result["weight_kg"] == 2070


def test_citroen_jumpy_zwei_radstaende():
    remarks = {
        "Bemerkungen Z9": "Zuordnung",
        "Bemerkungen Z10": "05) XFRHKH  /  XGRHKH",
        "Bemerkungen Z11": "44) 3000    /  3122",
    }
    kurz = resolve("VF7XFRHKH12345678", "VF7X.RHKH........", remarks)
    lang = resolve("VF7XGRHKH12345678", "VF7X.RHKH........", remarks)
    assert kurz["wheelbase_mm"] == 3000
    assert lang["wheelbase_mm"] == 3122


def test_unbekanntes_zeichen_ergibt_keine_zuordnung():
    # Position 7 ist "9" - kommt in der Zuordnung nicht vor
    assert resolve("W1K2239331A079835", MERCEDES_PATTERN, MERCEDES) == {}


def test_mehrere_luecken_bleiben_unaufgeloest():
    # Zwei offene Stellen lassen sich nicht eindeutig zuordnen
    assert resolve_index("W1K2231331A079835", "W1K22..33........",
                         ["I023T1", "I123T1"]) is None


def test_ohne_zuordnungstabelle_passiert_nichts():
    remarks = {"Bemerkungen Z1": "42) mit Niveauregulierung"}
    assert resolve("W1K2231331A079835", MERCEDES_PATTERN, remarks) == {}


def test_platzhalter_ist_kein_vin_zeichen():
    # "-" statt eines Zeichens: die Variante ist nicht ueber die VIN waehlbar
    remarks = {"Bemerkungen Z1": "05) V4W/-  /  V4W/A", "Bemerkungen Z2": "44) 1285  /  1280"}
    assert resolve("LL8ADV4WA12345678", "LL8ADV4W.........", remarks) == {}
