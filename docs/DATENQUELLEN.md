# Datenquellen und Lizenzprüfung (Phase 0)

Stand: 2026-09-08. Geprüft wurde für jede im Projektplan genannte Quelle, ob ein
**Import in die eigene Datenbank** zulässig ist. Maßstab ist die Lizenz des
Repositories bzw. die Rechtsnatur der Daten – nicht, ob ein Abruf technisch
möglich wäre.

Das Ergebnis ist zusätzlich in der Tabelle `sources` hinterlegt
(`db/migrations/002_seed_sources.sql`). Der ETL-Lauf bricht ab, wenn eine Quelle
mit `license_ok = false` importiert werden soll – die Prüfung ist also im Code
durchgesetzt und nicht nur dokumentiert.

## Freigegeben

| Quelle | Lizenz | Rolle | Auflage |
|---|---|---|---|
| [NHTSA vPIC](https://vpic.nhtsa.dot.gov/api) | gemeinfrei (Werk der US-Bundesregierung) | **Primäre WMI-Basis**, sekundäre Live-Quelle | Nennung als Quelle |
| [idlesign/vininfo](https://github.com/idlesign/vininfo) | BSD-3-Clause | herstellerspezifische VDS-Regeln (`manufacturer_patterns`) | Namensnennung (im Repo und in `sources.attribution`) |
| [cardog-ai/corgi](https://github.com/cardog-ai/corgi) | ISC | Referenz für Datenmodell und Cleaning | Namensnennung |
| [davidpeckham/vin](https://github.com/davidpeckham/vin) | MIT | US-Ergänzung | Namensnennung |
| [adaptant-labs/vin-decoder-dart](https://github.com/adaptant-labs/vin-decoder-dart) | Apache-2.0 | Quervergleich der Regeln | Namensnennung, Änderungsvermerk |

## Nicht importierbar

| Quelle | Befund | Konsequenz |
|---|---|---|
| [WALL-E/vin-decoder](https://github.com/WALL-E/vin-decoder) | **keine Lizenzdatei** im Repository | Ohne Lizenz gilt das Urheberrecht ungeschmälert. Die WMI-CSVs werden nicht importiert. Nur manueller Stichprobenvergleich. |
| [plowman/open-vehicle-db](https://github.com/plowman/open-vehicle-db) | **keine Lizenzdatei** | Kein Import. Der Zweck (Marke/Modell/Baujahr) wird durch vPIC abgedeckt, das gemeinfrei ist. |
| [louisevanderlith/vin](https://github.com/louisevanderlith/vin) | GPL-3.0 | Starkes Copyleft. Eine Übernahme würde das Gesamtprojekt binden – nur als Lektüre/Referenz. |
| CarAPI (Freemium) | proprietär | Bulk-Übernahme laut AGB unzulässig. Erst in Phase 6 als bezahlte Live-Quelle relevant. |
| vindecoder.eu, Fahrnex, AutoRef.eu, VINOPEN | AGB verbieten automatisierten Massenzugriff; zusätzlich greift voraussichtlich das EU-Datenbankschutzrecht (RL 96/9/EG) | Kein Scraping, kein Import – unabhängig vom Budget. Nutzung nur manuell als Referenz oder später als zahlender API-Kunde. |

Diese Zeile aus dem Projektplan bleibt die feste Grenze: für Quellen, die
automatisierten oder massenhaften Zugriff untersagen, wird kein Scraping
umgesetzt.

## Warum vPIC allein nicht reicht

Der Projektplan nimmt an, dass die kostenlose US-Quelle europäische Modelle nur
lückenhaft abdeckt. Die Annahme wurde beim Aufbau des Testsets überprüft und
bestätigt.

**Test 1 – WMI-Abfrage (`DecodeWMI`).** Diese europäischen Herstellerkennungen
sind in vPIC **nicht** hinterlegt:

| WMI | Hersteller | Land |
|---|---|---|
| `TMB` | Škoda | Tschechien |
| `TMA` | Hyundai (Nošovice) | Tschechien |
| `VSS` | SEAT | Spanien |
| `VF7` | Citroën | Frankreich |
| `SJN` | Nissan (Sunderland) | Großbritannien |

Vorhanden sind dagegen u. a. `WVW`, `WAU`, `WBA`, `WDB`, `W0L`, `VF1`, `VF3`,
`ZFA`, `ZAR`, `YV1`, `SAL`, `VNK` sowie für die Türkei `NM0` (Ford Otosan),
`NMT` (Toyota Türkiye) und `NLN` (Karsan).

**Test 2 – vollständige VIN-Abfrage (`DecodeVinValues`).** Von den 30 Fällen des
Testsets liefert vPIC bei **21** kein Modell. Beispiel VW Golf IV
(`WVWZZZ1JZ3W386752`): Hersteller, Marke, Baujahr und Werk kommen zurück, das
Feld `Model` bleibt leer.

Genau diese Lücke ist die Aufgabe der eigenen Datenbank. Deshalb wird vPIC in
`sources.reliability` und im NHTSA-Provider für Fahrzeuge im europäischen
Fokus bewusst niedriger gewichtet als für nordamerikanische.

## Namensnennung

Wird die Datenbank veröffentlicht oder das Tool öffentlich angeboten, sind
folgende Hinweise mitzuführen (sie stehen auch in `sources.attribution`):

- U.S. National Highway Traffic Safety Administration, vPIC
- vininfo, © Igor Starikov (idlesign), BSD-3-Clause
- corgi, cardog-ai, ISC License
- davidpeckham/vin, MIT License
- adaptant-labs/vin-decoder-dart, Apache License 2.0
