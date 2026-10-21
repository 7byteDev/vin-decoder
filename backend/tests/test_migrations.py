"""Leitplanken fuer das Schema, die ohne laufende Datenbank pruefbar sind."""

from __future__ import annotations

import re


def read_migrations(project_root) -> str:
    files = sorted((project_root / "db" / "migrations").glob("*.sql"))
    assert files, "keine Migrationen gefunden"
    return "\n".join(f.read_text(encoding="utf-8") for f in files)


def effective_patterns_index(sql: str) -> str:
    """Die zuletzt angelegte Fassung von idx_patterns_unique."""
    matches = re.findall(
        r"CREATE UNIQUE INDEX[^;]*idx_patterns_unique[^;]*;", sql, re.IGNORECASE | re.DOTALL
    )
    assert matches, "idx_patterns_unique wird nirgends angelegt"
    return matches[-1]


def test_pattern_index_keeps_ambiguous_alternatives(project_root):
    """Ein Muster darf mehrere Werte haben - sonst gehen Alternativen verloren.

    Regression: der erste Entwurf des Index liess pro Muster nur einen Wert
    zu und hat beim Import 872 von 4116 vininfo-Regeln verworfen.
    """
    index = effective_patterns_index(read_migrations(project_root))
    assert "value" in index, (
        "idx_patterns_unique muss die Spalte 'value' enthalten, sonst "
        "ueberschreiben mehrdeutige Regeln einander"
    )


def test_lookups_log_requires_the_mask(project_root):
    """Die Bedingung muss die Maske positiv verlangen.

    Regression: die erste Fassung pruefte "keine 17 gueltigen VIN-Zeichen".
    Da 'X' selbst ein gueltiges VIN-Zeichen ist, wies sie ausgerechnet die
    korrekt maskierten Werte ab - das Anfrage-Log blieb dauerhaft leer.
    """
    sql = read_migrations(project_root)
    constraints = re.findall(r"CHECK \(vin_masked[^)]*\)", sql)
    assert constraints, "keine Bedingung auf vin_masked gefunden"
    latest = constraints[-1]
    assert "XXXXXX$" in latest, f"Maske wird nicht verlangt: {latest}"
    assert "!~" not in latest, f"negative Formulierung ist fehleranfaellig: {latest}"


def test_mask_survives_its_own_constraint(project_root):
    """Was mask_vin() erzeugt, muss die Bedingung auch akzeptieren."""
    from app.decoder.structural import mask_vin

    sql = read_migrations(project_root)
    pattern = re.findall(r"CHECK \(vin_masked ~ '([^']+)'\)", sql)[-1]
    for vin in ("WVWZZZ1JZ3W386752", "TMBJB41Z4B2123456", "1HGCM82633A004352"):
        masked = mask_vin(vin)
        assert re.match(pattern, masked), f"{masked} scheitert an {pattern}"


def test_no_owner_or_registration_columns(project_root):
    """Datenschutz-Leitplanke: solche Spalten darf es im Schema nie geben.

    Kommentare werden vorher entfernt - dort steht bewusst, dass es diese
    Felder nicht gibt.
    """
    sql = read_migrations(project_root)
    without_comments = re.sub(r"--[^\n]*", "", sql).lower()
    for forbidden in ("owner", "holder", "halter", "license_plate", "kennzeichen", "registration"):
        assert forbidden not in without_comments, (
            f"verbotene Spalte/Bezeichnung im Schema: {forbidden}"
        )
