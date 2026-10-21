"""Baut das Test-VIN-Set (Phase 0) und reichert es mit einem vPIC-Abgleich an.

Ergebnis: ``qa/testset.json``. Jeder Fall haelt fest, was erwartet wird und
wie gut das abgesichert ist:

    verified = "vpic"        Marke/Hersteller ueber die WMI in vPIC bestaetigt
    verified = "structural"  aus ISO 3779/3780 hergeleitet (Land, Modelljahr)
    verified = "open"        Erwartung aus Fachwissen, in Phase 4 noch zu pruefen

Der Lauf haelt ausserdem fest, was vPIC selbst zur VIN liefert. Genau die
Faelle, in denen vPIC kein Modell kennt, sind die Luecke, die die eigene
Datenbank schliessen soll.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.decoder.structural import decode_structural  # noqa: E402

OUT = ROOT / "qa" / "testset.json"
VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues"

# vin, Land, Modelljahr (None = mehrdeutig), Marke, Modell, Absicherung, Notiz
CASES: list[tuple] = [
    # --- Deutschland ------------------------------------------------------
    ("WVWZZZ1JZ3W386752", "DE", 2003, "Volkswagen", "Golf IV", "vpic", "Plattform 1J"),
    ("WVWZZZ3CZFE123456", "DE", 2015, "Volkswagen", "Passat", "vpic", "Plattform 3C"),
    ("WAUZZZ8K9BA123456", "DE", 2011, "Audi", "A4", "vpic", "Plattform 8K"),
    ("WBA3B1C50EK123456", "DE", 2014, "BMW", "3er", "vpic", ""),
    ("WDB2110563A123456", "DE", 2003, "Mercedes-Benz", "E-Klasse", "vpic", "Baureihe W211"),
    ("W0LPD6EL5B1123456", "DE", 2011, "Opel", "Astra J", "open",
     "vininfo-Regeln: Modellcode P an Position 4"),
    ("WP0ZZZ99ZAS123456", "DE", 2010, "Porsche", "911", "open", ""),
    ("WMWZC3C50EWP12345", "DE", 2014, "MINI", None, "open", "Fertigung Oxford, WMI Deutschland"),
    # --- Frankreich -------------------------------------------------------
    ("VF1LM1B0H36123456", "FR", 2003, "Renault", None, "vpic",
     "vininfo liefert Karosserie/Getriebe-Regeln"),
    ("VF3LCBHZBHS123456", "FR", 2017, "Peugeot", None, "vpic", ""),
    ("VF7DD5FS8CJ123456", "FR", 2012, "Citroen", None, "open",
     "LUECKE: VF7 ist in vPIC nicht hinterlegt"),
    ("VNKKTUD35FA123456", "FR", 2015, "Toyota", "Yaris", "vpic", "Toyota Valenciennes"),
    # --- Italien / Spanien / Tschechien ----------------------------------
    ("ZFA312000E1123456", "IT", 2014, "Fiat", None, "vpic", ""),
    ("ZAR939000E7123456", "IT", 2014, "Alfa Romeo", None, "vpic", ""),
    ("VSSZZZ6JZ8R123456", "ES", 2008, "SEAT", "Ibiza", "open",
     "LUECKE: VSS ist in vPIC nicht hinterlegt"),
    ("TMBJB41Z4B2123456", "CZ", 2011, "Skoda", "Octavia", "open",
     "LUECKE: TMB ist in vPIC nicht hinterlegt"),
    ("TMAD381AAFJ123456", "CZ", 2015, "Hyundai", "i30", "open",
     "LUECKE: TMA (Hyundai Nosovice) ist in vPIC nicht hinterlegt"),
    ("U5YFF241ADL123456", "SK", 2013, "Kia", "Ceed", "open",
     "Konfliktfall: Land strukturell SK, vPIC ordnet U5Y einem US-Standort zu"),
    # --- Nordeuropa / UK --------------------------------------------------
    ("YV1MS672382123456", "SE", 2008, "Volvo", "S40", "vpic", ""),
    ("YS3DD78N4X7055320", "SE", 1999, "Saab", "9-3", "vpic", ""),
    ("SALLDHMP7VA123456", "GB", None, "Land Rover", "Discovery", "vpic",
     "Jahrescode V ist mehrdeutig (1997/2027) - Testfall fuer Mehrdeutigkeit"),
    ("SJNFAAJ11D1234567", "GB", 2013, "Nissan", "Qashqai", "open",
     "LUECKE: SJN (Nissan Sunderland) ist in vPIC nicht hinterlegt"),
    # --- Tuerkei ----------------------------------------------------------
    ("NM0LS7E28E1234567", "TR", 2014, "Ford", "Transit Connect", "vpic",
     "Ford Otosan, Golcuk"),
    ("NMTKZ3BXXMR123456", "TR", 2021, "Toyota", "C-HR", "vpic",
     "Toyota Motor Manufacturing Turkey, Sakarya"),
    ("NLNMDBFC5N1123456", "TR", 2022, "Karsan", None, "vpic", "Karsan, Bursa"),
    # --- Osteuropa --------------------------------------------------------
    ("XTA21099062123456", "RU", 2006, "Lada", "2109", "open",
     "vininfo-Regeln fuer AvtoVAZ vorhanden"),
    # --- Nordamerika (Pruefziffer verbindlich) ----------------------------
    ("1HGCM82633A004352", "US", 2003, "Honda", "Accord", "vpic",
     "Referenz-VIN der NHTSA, Pruefziffer korrekt"),
    ("JHMCM56557C404453", "JP", 2007, "Honda", "Accord", "vpic", ""),
    ("1FTFW1ET5DFC10312", "US", 2013, "Ford", "F-150", "vpic", ""),
    ("5YJ3E1EA7JF005339", "US", 2018, "Tesla", "Model 3", "vpic", ""),
]


async def snapshot(vins: list[str]) -> dict[str, dict]:
    """Was liefert vPIC selbst? (Nur zur Dokumentation der Luecken.)"""
    out: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=25) as client:
        for vin in vins:
            try:
                response = await client.get(f"{VPIC}/{vin}", params={"format": "json"})
                data = (response.json().get("Results") or [{}])[0]
            except Exception as exc:
                out[vin] = {"error": str(exc)}
                continue
            out[vin] = {
                key: data.get(key) or None
                for key in (
                    "Make", "Model", "ModelYear", "Manufacturer", "PlantCountry", "ErrorCode",
                )
            }
    return out


def main() -> int:
    vins = [c[0] for c in CASES]
    vpic = asyncio.run(snapshot(vins))

    cases = []
    problems = []
    for vin, country, year, make, model, verified, note in CASES:
        result = decode_structural(vin)
        if result.country_code != country:
            problems.append(f"{vin}: Land erwartet {country}, strukturell {result.country_code}")
        if year is not None and result.model_year != year:
            problems.append(
                f"{vin}: Jahr erwartet {year}, strukturell {result.model_year} "
                f"(Kandidaten {result.model_year_candidates})"
            )
        snap = vpic.get(vin, {})
        cases.append(
            {
                "vin": vin,
                "expect": {
                    "country_code": country,
                    "model_year": year,
                    "make": make,
                    "model": model,
                },
                "verified": verified,
                "notes": note,
                "structural": {
                    "wmi": result.wmi,
                    "country": result.country,
                    "model_year_candidates": result.model_year_candidates,
                    "check_digit_valid": result.check_digit_valid,
                    "check_digit_required": result.check_digit_required,
                },
                "vpic_snapshot": snap,
                "vpic_knows_model": bool(snap.get("Model")),
            }
        )

    payload = {
        "meta": {
            "purpose": "Genauigkeitsmessung des VIN-Decoders (Projektplan Phase 0 und 4)",
            "privacy": "Nur technische Muster. Die Seriennummern sind Platzhalter, "
                       "es sind keine realen Einzelfahrzeuge referenziert.",
            "verification_levels": {
                "vpic": "Hersteller/Marke ueber die WMI in NHTSA vPIC bestaetigt",
                "structural": "aus ISO 3779/3780 hergeleitet",
                "open": "Fachwissen, in Phase 4 manuell zu bestaetigen",
            },
            "case_count": len(cases),
            "vpic_without_model": sum(1 for c in cases if not c["vpic_knows_model"]),
        },
        "cases": cases,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{len(cases)} Faelle -> {OUT}")
    without = payload["meta"]["vpic_without_model"]
    print(f"vPIC kennt bei {without} von {len(cases)} Faellen kein Modell.")
    if problems:
        print("\nAbweichungen zwischen Erwartung und struktureller Decodierung:")
        for p in problems:
            print("  -", p)
        return 1
    print("Alle Erwartungen zu Land und Modelljahr stimmen mit der Struktur ueberein.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
