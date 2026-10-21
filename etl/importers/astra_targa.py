"""Importer: Schweizer Typengenehmigungen (ASTRA TARGA, Open Government Data).

Das ist die Quelle, die den technischen Teil des Decoders traegt. Die
Datei ``TG-Automobil.txt`` enthaelt pro Typengenehmigung eine Zeile mit
224 Spalten - darunter in "06 Vorziffer" ein VIN-Muster mit Punkten als
Platzhalter:

    VF1RJA...........   Renault Clio, 999 ccm, 67 kW, Benzin
    ZAR939000........   Alfa Romeo ...

Damit laesst sich eine Fahrgestellnummer auf Motor, Getriebe, Abmessungen
und Gewichte abbilden - genau die Daten, die keine der bisherigen freien
Quellen fuer europaeische Fahrzeuge liefert.

Ablauf:
    1. Datei streamen und im Cache ablegen (308 MB, nur bei Aenderung neu)
    2. Zeilen parsen, Felder normalisieren, Abschnitte nach der offiziellen
       Feldliste des ASTRA gruppieren
    3. Alte Zeilen dieser Quelle loeschen, neue per COPY einspielen

Der Import ist ein Vollabzug: die Datei ist ein woechentlicher Snapshot,
ein Delta-Verfahren waere unnoetig kompliziert und fehleranfaellig.
"""

from __future__ import annotations

import csv
import json
import logging
import pathlib
import re
import sys
from collections.abc import Iterator
from datetime import date
from typing import Any

import asyncpg
import httpx

from ..common import DATA_DIR, RAW_DIR, finish_source, source_id

logger = logging.getLogger("etl.targa")

SOURCE_KEY = "astra_targa"

BASE_URL = (
    "https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA"
    "/2200-Basisdaten_TG_ab_1995"
)
DATASETS = {
    "automobil": "TG-Automobil.txt",
    "moto": "TG-Moto.txt",
    "anhaenger": "TG-Anhaenger.txt",
    "verbrauch": "verbrauch.txt",
    "emissionen": "emissionen.txt",
}

CACHE_DIR = RAW_DIR / "astra_targa"
FIELD_MAP_FILE = DATA_DIR / "targa_fields.json"

#: Spaltenueberschrift -> Feld in type_approvals
COLUMNS = {
    "approval_number": "Typengenehmigungsnummer",
    "approval_date": "Typengenehmigung erteilt",
    "eu_approval_number": "09 EU-Gesamtgenehmigung",
    "vin_pattern": "06 Vorziffer",
    "make": "04 Marke",
    "model": "04 Typ",
    "variant": "05 Typ; Variante/Version",
    "manufacturer": "10 Hersteller",
    "vehicle_kind": "01 Fahrzeugart",
    "vehicle_class": "03 Fahrzeugklasse",
    "body_form": "07 Karosserieform",
    "offroad": "08 Gel\xe4ndefahrzeug",
    "engine_make": "25 Motor Marke",
    "engine_model": "25 Motor Typ",
    "engine_code": "34 Motorkennzeichen",
    "engine_design": "26 Bauart",
    "fuel_code": "26 Bauart Treibstoff",
    "displacement": "27 Hubraum",
    "power_kw": "28 Leistung kW",
    "power_rpm": "28 Leistung n",
    "torque_nm": "29 Md. max Nm",
    "torque_rpm": "29 Md. max n",
    "drive": "17 Achsantrieb",
    "transmission": "18 Getriebe 1",
    "doors": "38 Anzahl T\xfcren",
    "seats": "37 Anzahl Pl\xe4tze Total von",
    "vmax": "19 Fahrzeug Vmax mech von",
    "length": "40 L\xe4nge von",
    "width": "41 Breite von",
    "height": "42 H\xf6he von",
    "wheelbase": "44 Abstand Achse 1-2 von",
    "weight": "52 Leergewicht von",
    "max_weight": "53 Garantiegewicht von",
}

#: Treibstoffcode -> kanonischer Schluessel (das Frontend uebersetzt ihn).
#: Empirisch aus dem Datensatz bestimmt; unbekannte Codes bleiben roh.
FUEL_CODES = {
    "B": "petrol",
    "C": "petrol_direct_injection",
    "D": "diesel",
    "E": "electric",
    "G": "gas",
    "H": "hybrid",
    "W": "hydrogen",
}

#: TARGA codiert die Antriebsart als einzelnen Buchstaben, teils mit
#: Zusatz ("A; vorne ausschaltbar", "H; A3"). Massgeblich ist der erste
#: Teil vor dem Semikolon.
DRIVE_CODES = {"V": "front_wheel", "H": "rear_wheel", "A": "all_wheel"}

DRIVE_TYPES = [
    (re.compile(r"allrad|4x4|4wd", re.I), "all_wheel"),
    (re.compile(r"vorderrad|^vorne|front", re.I), "front_wheel"),
    (re.compile(r"hinterrad|^hinten|heck", re.I), "rear_wheel"),
]

TRANSMISSION_KINDS = {"m": "manual", "a": "automatic", "s": "continuous", "e": "electric"}


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _meta_path(name: str) -> pathlib.Path:
    return CACHE_DIR / f"{name}.meta.json"


def download(
    name: str = "automobil", *, force: bool = False, timeout: float = 60.0
) -> pathlib.Path:
    """Datensatz herunterladen, wenn er sich geaendert hat.

    Verglichen werden Groesse und Last-Modified aus dem HEAD-Request. Bei
    308 MB lohnt es sich, einen unveraenderten Snapshot nicht erneut zu ziehen.
    """
    filename = DATASETS[name]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / filename
    meta_file = _meta_path(name)
    url = f"{BASE_URL}/{filename}"

    headers = {"User-Agent": "vin-decoder-etl/0.1 (+ukm.net.tr)"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        head = client.head(url)
        head.raise_for_status()
        remote = {
            "size": head.headers.get("content-length"),
            "last_modified": head.headers.get("last-modified"),
        }

        if not force and target.exists() and meta_file.exists():
            local = json.loads(meta_file.read_text(encoding="utf-8"))
            if local == remote and target.stat().st_size == int(remote["size"] or 0):
                logger.info("%s ist aktuell (%s Bytes) - kein Download.", filename, remote["size"])
                return target

        total = int(remote["size"] or 0)
        logger.info("Lade %s (%.0f MB) ...", filename, total / 1_048_576 if total else 0)
        tmp = target.with_suffix(".part")
        done = 0
        step = 0
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_bytes(1 << 20):
                    handle.write(chunk)
                    done += len(chunk)
                    if total and done // (50 << 20) > step:
                        step = done // (50 << 20)
                        logger.info("  %.0f / %.0f MB", done / 1_048_576, total / 1_048_576)
        tmp.replace(target)
        meta_file.write_text(json.dumps(remote), encoding="utf-8")

    logger.info("%s geladen (%s Bytes).", filename, target.stat().st_size)
    return target


# ---------------------------------------------------------------------------
# Parsen
# ---------------------------------------------------------------------------


def load_field_sections() -> dict[str, str]:
    """Spaltenueberschrift -> Abschnitt, aus der ASTRA-Feldliste."""
    if not FIELD_MAP_FILE.exists():
        return {}
    entries = json.loads(FIELD_MAP_FILE.read_text(encoding="utf-8"))
    return {e["label"]: e["section"] for e in entries if e.get("label")}


#: Wertebereich einer PostgreSQL-Spalte vom Typ smallint
SMALLINT_MIN, SMALLINT_MAX = -32768, 32767


def _int(value: str | None) -> int | None:
    """Erste ganze Zahl im Feld.

    TARGA schreibt in manche Zahlenfelder Text, z. B. bei den Tueren
    "'2+1 / 4+1" oder "'2-4" (das fuehrende Apostroph ist eine
    Excel-Textmarkierung). Alle Ziffern zusammenzukleben ergaebe 2141 -
    gemeint sind zwei Tueren. Deshalb wird die erste Zahl genommen.
    """
    if not value:
        return None
    match = re.search(r"\d+(?:[.,]\d+)?", value)
    if not match:
        return None
    number = round(float(match.group(0).replace(",", ".")))
    return number or None


def _smallint(value: str | None, *, label: str = "") -> int | None:
    """Wie _int, aber nur wenn der Wert in eine smallint-Spalte passt."""
    number = _int(value)
    if number is None:
        return None
    if not SMALLINT_MIN <= number <= SMALLINT_MAX:
        logger.warning("Wert ausserhalb smallint (%s): %r -> ignoriert", label, value)
        return None
    return number


def _float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", ".").strip()
    try:
        number = float(re.sub(r"[^\d.-]", "", cleaned))
    except ValueError:
        return None
    return number or None


def _date(value: str | None) -> date | None:
    if not value or len(value.strip()) != 8 or not value.strip().isdigit():
        return None
    text = value.strip()
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def normalize_fuel(code: str | None) -> str | None:
    if not code:
        return None
    return FUEL_CODES.get(code.strip().upper(), code.strip())


def normalize_drive(text: str | None) -> str | None:
    """'V' -> front_wheel, 'A; vorne ausschaltbar' -> all_wheel."""
    if not text:
        return None
    head = text.split(";")[0].strip()
    if head.upper() in DRIVE_CODES:
        return DRIVE_CODES[head.upper()]
    for pattern, key in DRIVE_TYPES:
        if pattern.search(head):
            return key
    return head or None


def parse_transmission(text: str | None) -> tuple[str | None, int | None]:
    """'m6' -> ('manual', 6); 'a8' -> ('automatic', 8)."""
    if not text:
        return None, None
    cleaned = text.strip().lower()
    match = re.match(r"([a-z]+)\s*(\d+)?", cleaned)
    if not match:
        return cleaned or None, None
    kind = TRANSMISSION_KINDS.get(match.group(1)[:1], match.group(1))
    gears = int(match.group(2)) if match.group(2) else None
    return kind, gears or None


def split_vin_pattern(pattern: str) -> tuple[str, str, str | None] | None:
    """'VF1RJA...........' -> (Muster, Praefix, Regex oder None).

    Steht der feste Teil komplett vorn, reicht der Praefix fuer die Suche.
    Stehen Platzhalter mitten drin, wird zusaetzlich ein Regex gebraucht.
    """
    cleaned = (pattern or "").strip().upper()
    if not cleaned:
        return None
    # Platzhalter sind Punkte, gelegentlich auch '?' oder '*'
    normalized = re.sub(r"[?*]", ".", cleaned)
    normalized = re.sub(r"[^A-Z0-9.]", "", normalized)
    prefix = normalized.split(".", 1)[0]
    if len(prefix) < 2:
        return None
    has_inner = "." in normalized and normalized.rstrip(".") != prefix
    regex = None
    if has_inner:
        body = normalized.rstrip(".")
        regex = "^" + "".join(("." if ch == "." else re.escape(ch)) for ch in body)
    return normalized, prefix[:17], regex


def parse(path: pathlib.Path) -> Iterator[dict[str, Any]]:
    """Zeilen des TARGA-Datensatzes als Dicts liefern."""
    sections = load_field_sections()
    # TARGA liefert Windows-Kodierung; Zeilen enthalten keine Quotes.
    with path.open("r", encoding="cp1252", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = [h.strip() for h in next(reader)]
        index = {name: i for i, name in enumerate(header) if name}

        missing = [label for label in COLUMNS.values() if label not in index]
        if missing:
            raise SystemExit(
                "TARGA-Datensatz hat ein anderes Format als erwartet, fehlende Spalten: "
                + ", ".join(missing)
            )

        def value(row: list[str], key: str) -> str | None:
            position = index.get(COLUMNS[key])
            if position is None or position >= len(row):
                return None
            text = row[position].strip()
            return text or None

        for row in reader:
            if len(row) < len(header) // 2:
                continue
            approval = value(row, "approval_number")
            if not approval:
                continue

            # kompletter Datensatz, nach den offiziellen Themen gruppiert
            specs: dict[str, dict[str, str]] = {}
            for label, position in index.items():
                if position >= len(row):
                    continue
                text = row[position].strip()
                if not text:
                    continue
                section = sections.get(label, "Sonstiges")
                specs.setdefault(section, {})[label] = text

            transmission, gears = parse_transmission(value(row, "transmission"))
            approval_date = _date(value(row, "approval_date"))
            yield {
                "approval_number": approval,
                "approval_date": approval_date,
                "eu_approval_number": value(row, "eu_approval_number"),
                "vin_pattern": value(row, "vin_pattern"),
                "make": value(row, "make"),
                "model": value(row, "model"),
                "variant": value(row, "variant"),
                "manufacturer": value(row, "manufacturer"),
                "vehicle_kind": value(row, "vehicle_kind"),
                "vehicle_class": value(row, "vehicle_class"),
                "body_form": value(row, "body_form"),
                "is_offroad": bool(value(row, "offroad")),
                "engine_make": value(row, "engine_make"),
                "engine_model": value(row, "engine_model"),
                "engine_code": value(row, "engine_code"),
                "engine_design": value(row, "engine_design"),
                "fuel_code": value(row, "fuel_code"),
                "fuel_type": normalize_fuel(value(row, "fuel_code")),
                "displacement_ccm": _int(value(row, "displacement")),
                "power_kw": _float(value(row, "power_kw")),
                "power_rpm": _int(value(row, "power_rpm")),
                "torque_nm": _smallint(value(row, "torque_nm"), label="torque_nm"),
                "torque_rpm": _smallint(value(row, "torque_rpm"), label="torque_rpm"),
                "drive_type": normalize_drive(value(row, "drive")),
                "transmission": transmission,
                "gears": gears,
                "doors": _smallint(value(row, "doors"), label="doors"),
                "seats_total": _smallint(value(row, "seats"), label="seats"),
                "top_speed_kmh": _smallint(value(row, "vmax"), label="vmax"),
                "length_mm": _int(value(row, "length")),
                "width_mm": _int(value(row, "width")),
                "height_mm": _int(value(row, "height")),
                "wheelbase_mm": _int(value(row, "wheelbase")),
                "weight_kg": _int(value(row, "weight")),
                "max_weight_kg": _int(value(row, "max_weight")),
                "model_year_from": approval_date.year if approval_date else None,
                "specs": specs,
            }


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------

APPROVAL_COLUMNS = (
    "id", "source_id", "approval_number", "approval_date", "eu_approval_number",
    "make", "model", "variant", "manufacturer", "vehicle_kind", "vehicle_class",
    "body_form", "is_offroad", "engine_make", "engine_model", "engine_code",
    "engine_design", "fuel_code", "fuel_type", "displacement_ccm", "power_kw",
    "power_rpm", "torque_nm", "torque_rpm", "drive_type", "transmission", "gears",
    "doors", "seats_total", "top_speed_kmh", "length_mm", "width_mm", "height_mm",
    "wheelbase_mm", "weight_kg", "max_weight_kg", "model_year_from", "specs",
)

PATTERN_COLUMNS = ("type_approval_id", "pattern", "prefix", "regex")


async def run(
    conn: asyncpg.Connection,
    *,
    dataset: str = "automobil",
    force_download: bool = False,
    limit: int | None = None,
) -> int:
    sid = await source_id(conn, SOURCE_KEY)
    path = download(dataset, force=force_download)

    logger.info("Lese %s ...", path.name)
    start_id = await conn.fetchval("SELECT last_value + 1 FROM type_approvals_id_seq")

    approvals: list[tuple] = []
    patterns: list[tuple] = []
    without_pattern = 0
    next_id = int(start_id)

    for record in parse(path):
        if limit and len(approvals) >= limit:
            break
        row_id = next_id
        next_id += 1
        approvals.append(
            (
                row_id, sid, record["approval_number"], record["approval_date"],
                record["eu_approval_number"], record["make"], record["model"],
                record["variant"], record["manufacturer"], record["vehicle_kind"],
                record["vehicle_class"], record["body_form"], record["is_offroad"],
                record["engine_make"], record["engine_model"], record["engine_code"],
                record["engine_design"], record["fuel_code"], record["fuel_type"],
                record["displacement_ccm"], record["power_kw"], record["power_rpm"],
                record["torque_nm"], record["torque_rpm"], record["drive_type"],
                record["transmission"], record["gears"], record["doors"],
                record["seats_total"], record["top_speed_kmh"], record["length_mm"],
                record["width_mm"], record["height_mm"], record["wheelbase_mm"],
                record["weight_kg"], record["max_weight_kg"], record["model_year_from"],
                json.dumps(record["specs"], ensure_ascii=False),
            )
        )
        split = split_vin_pattern(record["vin_pattern"] or "")
        if split:
            pattern, prefix, regex = split
            patterns.append((row_id, pattern, prefix, regex))
        else:
            without_pattern += 1

        if len(approvals) % 50_000 == 0:
            logger.info("  %s Zeilen gelesen ...", len(approvals))

    logger.info(
        "%s Genehmigungen, %s VIN-Muster (%s Zeilen ohne Muster).",
        len(approvals), len(patterns), without_pattern,
    )
    if not approvals:
        raise SystemExit("Keine Zeilen gelesen - Import abgebrochen.")

    async with conn.transaction():
        deleted = await conn.execute("DELETE FROM type_approvals WHERE source_id = $1", sid)
        logger.info("Alter Bestand entfernt (%s).", deleted)
        await conn.copy_records_to_table(
            "type_approvals", records=approvals, columns=list(APPROVAL_COLUMNS)
        )
        await conn.copy_records_to_table(
            "type_approval_vin_patterns", records=patterns, columns=list(PATTERN_COLUMNS)
        )
        await conn.execute("SELECT setval('type_approvals_id_seq', $1)", next_id)

    await finish_source(conn, SOURCE_KEY, len(approvals))
    logger.info("TARGA-Import fertig: %s Genehmigungen in der Datenbank.", len(approvals))
    return len(approvals)


if __name__ == "__main__":  # pragma: no cover - manueller Probelauf
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    target = download("automobil")
    for i, entry in enumerate(parse(target)):
        if i >= 3:
            break
        print(json.dumps(entry, ensure_ascii=False, default=str)[:600])
    sys.exit(0)


# ---------------------------------------------------------------------------
# Verbrauch und Emissionen
# ---------------------------------------------------------------------------

#: In beiden Zusatzdatensaetzen steht 0 fuer "nicht zutreffend" - ein
#: Verbrenner hat keine WLTP-Stromreichweite, ein Oldtimer keine
#: WLTP-Werte. Als echte Null wuerde das die Anzeige verfaelschen.
def _positive(value: str | None) -> float | None:
    number = _float(value)
    return number if number and number > 0 else None


def _positive_int(value: str | None) -> int | None:
    number = _int(value)
    return number if number and number > 0 else None


EXTRA_COLUMNS = {
    "consumption": {
        "approval": "TG-Code",
        "fuel": "Treibstoff",
        "transmission": "Getriebe",
        "axle": "iAchse",
        "efficiency": "Energieeffizienzkategorie",
        "consumption": "ET_Verbrauch",
        "co2": "ET_CO2",
        "consumption_wltp": "ET_Verbrauch_WLTP",
        "co2_wltp": "ET_CO2_WLTP",
        "electric": "EL_Verbrauch_WLTP",
        "range": "EL_Reichweite_bis_WLTP",
        "electric_nedc": "EL_Verbrauch",
        "range_nedc": "EL_Reichweite_bis",
    },
    "emissions": {
        "approval": "TG-Code",
        "fuel": "Treibstoff",
        "transmission": "Getriebe",
        "axle": "iAchse",
        "emission_code": "Emissionscode",
        "exhaust_code": "AbgasCode",
        "cylinders": "Anz_Zylinder",
        "displacement": "Hubraum",
        "power": "Leistung",
    },
}

EXTRA_INSERT_COLUMNS = (
    "source_id", "approval_number", "kind", "fuel_code", "fuel_type",
    "transmission", "axle_ratio", "consumption_l100", "co2_g_km",
    "consumption_wltp_l100", "co2_wltp_g_km", "electric_kwh100",
    "electric_range_km", "efficiency_category", "emission_code",
    "exhaust_code", "cylinders", "displacement_ccm", "power_kw", "data",
)


def parse_extras(path: pathlib.Path, kind: str) -> Iterator[tuple]:
    """Zeilen von verbrauch.txt bzw. emissionen.txt aufbereiten."""
    mapping = EXTRA_COLUMNS[kind]
    with path.open("r", encoding="cp1252", errors="replace", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = [h.strip() for h in next(reader)]
        index = {name: i for i, name in enumerate(header) if name}

        if mapping["approval"] not in index:
            raise SystemExit(f"{path.name}: Spalte '{mapping['approval']}' fehlt")

        def value(row: list[str], key: str) -> str | None:
            position = index.get(mapping.get(key, ""))
            if position is None or position >= len(row):
                return None
            return row[position].strip() or None

        for row in reader:
            approval = value(row, "approval")
            if not approval:
                continue
            data = {
                label: row[position].strip()
                for label, position in index.items()
                if position < len(row) and row[position].strip()
            }
            transmission, _ = parse_transmission(value(row, "transmission"))
            fuel_code = value(row, "fuel")
            yield (
                approval,
                fuel_code,
                normalize_fuel(fuel_code),
                transmission,
                value(row, "axle"),
                _positive(value(row, "consumption")),
                _positive_int(value(row, "co2")),
                _positive(value(row, "consumption_wltp")),
                _positive_int(value(row, "co2_wltp")),
                _positive(value(row, "electric")) or _positive(value(row, "electric_nedc")),
                _positive_int(value(row, "range")) or _positive_int(value(row, "range_nedc")),
                value(row, "efficiency"),
                value(row, "emission_code"),
                value(row, "exhaust_code"),
                _positive_int(value(row, "cylinders")),
                _positive_int(value(row, "displacement")),
                _positive(value(row, "power")),
                json.dumps(data, ensure_ascii=False),
            )


async def run_extras(
    conn: asyncpg.Connection, *, kind: str, force_download: bool = False
) -> int:
    """verbrauch.txt oder emissionen.txt einspielen (Vollabzug)."""
    dataset = "verbrauch" if kind == "consumption" else "emissionen"
    sid = await source_id(conn, SOURCE_KEY)
    path = download(dataset, force=force_download)

    logger.info("Lese %s ...", path.name)
    records = [
        (sid, row[0], kind, *row[1:]) for row in parse_extras(path, kind)
    ]
    logger.info("%s: %s Zeilen", path.name, len(records))
    if not records:
        raise SystemExit(f"{path.name}: keine Zeilen gelesen")

    async with conn.transaction():
        await conn.execute(
            "DELETE FROM type_approval_extras WHERE source_id = $1 AND kind = $2", sid, kind
        )
        await conn.copy_records_to_table(
            "type_approval_extras", records=records, columns=list(EXTRA_INSERT_COLUMNS)
        )

    matched = await conn.fetchval(
        """
        SELECT count(DISTINCT e.approval_number) FROM type_approval_extras e
        WHERE e.kind = $1
          AND EXISTS (SELECT 1 FROM type_approvals t
                       WHERE t.approval_number = e.approval_number)
        """,
        kind,
    )
    logger.info(
        "%s fertig: %s Zeilen, %s Genehmigungen zugeordnet.", kind, len(records), matched
    )
    return len(records)
