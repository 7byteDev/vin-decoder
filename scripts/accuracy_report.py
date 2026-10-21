"""Genauigkeitsmessung gegen das Test-VIN-Set (Projektplan Phase 4).

    python scripts/accuracy_report.py                # nur Struktur + Live-API
    python scripts/accuracy_report.py --no-live      # rein offline
    python scripts/accuracy_report.py --json qa/accuracy.json

Gemessen wird je Attribut die Trefferquote gegen ``qa/testset.json``.
Faelle, deren Erwartung selbst noch nicht bestaetigt ist (``verified`` =
"open"), werden getrennt ausgewiesen - sie sind ein Hinweis auf zu
pruefende Erwartungen, nicht auf Fehler des Decoders.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.decoder.engine import decode  # noqa: E402
from app.decoder.types import Attr  # noqa: E402
from app.sources.db_provider import DatabaseProvider  # noqa: E402
from app.sources.nhtsa import NhtsaProvider  # noqa: E402
from app.sources.type_approval import TypeApprovalProvider  # noqa: E402

TESTSET = ROOT / "qa" / "testset.json"

CHECKED = (
    ("country_code", Attr.COUNTRY_CODE),
    ("model_year", Attr.MODEL_YEAR),
    ("make", Attr.MAKE),
    ("model", Attr.MODEL),
)


def normalize(value: object) -> str:
    """Vergleichsform ohne Diakritika.

    Sonst gelten 'Skoda'/'Škoda' und 'Citroen'/'Citroën' als Abweichung,
    obwohl der Decoder richtig liegt - das waere ein Messfehler, kein Treffer.
    """
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.strip().casefold().split())


def matches(expected: object, actual: object) -> bool:
    left, right = normalize(expected), normalize(actual)
    if not left or not right:
        return False
    return left == right or left in right or right in left


async def run(live: bool, as_json: pathlib.Path | None) -> int:
    if not TESTSET.exists():
        print("qa/testset.json fehlt - 'python etl/build_testset.py' ausfuehren.")
        return 1

    cases = json.loads(TESTSET.read_text(encoding="utf-8"))["cases"]
    settings = get_settings()

    db = Database(settings.asyncpg_dsn)
    connected = await db.connect()
    # dieselbe Kette wie die API, sonst misst der Bericht etwas anderes
    db_providers = [DatabaseProvider(db), TypeApprovalProvider(db)] if connected else []
    live_providers = (
        [NhtsaProvider(base_url=settings.nhtsa_base_url, timeout=settings.nhtsa_timeout_seconds)]
        if live
        else []
    )

    totals = {name: [0, 0] for name, _ in CHECKED}   # [Treffer, pruefbare Faelle]
    open_totals = {name: [0, 0] for name, _ in CHECKED}
    rows = []

    try:
        for case in cases:
            outcome = await decode(
                case["vin"],
                db_providers=db_providers,
                live_providers=live_providers,
                allow_live=live,
            )
            row = {"vin": case["vin"], "verified": case["verified"], "results": {}}
            for name, attribute in CHECKED:
                expected = case["expect"].get(name)
                if expected is None:
                    continue
                field = outcome.fields.get(attribute)
                hit = matches(expected, field.value if field else None)
                bucket = totals if case["verified"] != "open" else open_totals
                bucket[name][1] += 1
                bucket[name][0] += int(hit)
                row["results"][name] = {
                    "expected": expected,
                    "actual": field.value if field else None,
                    "confidence": field.confidence if field else 0.0,
                    "hit": hit,
                }
            row["overall_confidence"] = outcome.confidence
            row["sources"] = outcome.sources_used
            rows.append(row)
    finally:
        await db.disconnect()

    mode = []
    mode.append("Datenbank" if connected else "keine Datenbank")
    mode.append("Live-API" if live else "offline")
    print(f"Testset: {len(cases)} Faelle  |  Modus: {', '.join(mode)}\n")

    print(f"{'Attribut':<16}{'bestaetigt':>14}{'offen':>14}")
    for name, _ in CHECKED:
        hit, total = totals[name]
        ohit, ototal = open_totals[name]
        confirmed = f"{hit}/{total}" + (f" ({hit / total:.0%})" if total else "")
        openness = f"{ohit}/{ototal}" + (f" ({ohit / ototal:.0%})" if ototal else "")
        print(f"{name:<16}{confirmed:>14}{openness:>14}")

    misses = [
        (row["vin"], name, data["expected"], data["actual"])
        for row in rows
        for name, data in row["results"].items()
        if not data["hit"]
    ]
    if misses:
        print(f"\nAbweichungen ({len(misses)}):")
        for vin, name, expected, actual in misses:
            print(f"  {vin}  {name:<14} erwartet {expected!r:<22} erhalten {actual!r}")

    average = sum(r["overall_confidence"] for r in rows) / max(1, len(rows))
    print(f"\nDurchschnittliche Gesamtkonfidenz: {average:.2f}")

    if as_json:
        as_json.parent.mkdir(parents=True, exist_ok=True)
        as_json.write_text(
            json.dumps(
                {
                    "mode": {"database": connected, "live": live},
                    "totals": {k: {"hits": v[0], "checked": v[1]} for k, v in totals.items()},
                    "open": {k: {"hits": v[0], "checked": v[1]} for k, v in open_totals.items()},
                    "average_confidence": round(average, 4),
                    "cases": rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Bericht geschrieben: {as_json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-live", action="store_true", help="keine externen APIs abfragen")
    parser.add_argument("--json", type=pathlib.Path, default=None, help="Bericht als JSON ablegen")
    args = parser.parse_args()
    os.environ.setdefault("LOG_LOOKUPS", "false")
    return asyncio.run(run(live=not args.no_live, as_json=args.json))


if __name__ == "__main__":
    raise SystemExit(main())
