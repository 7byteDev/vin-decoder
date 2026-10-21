# VIN-Decoder – Kurzbeschreibung & Projektplan

## Kurzbeschreibung

Ein webbasiertes, mehrsprachiges (EN/DE/TR) VIN-Decoder-Tool mit modernem, minimalistischem Design. Kernstück ist eine eigene PostgreSQL-Datenbank, die aus offenen GitHub-VIN-Datensätzen aufgebaut und laufend über freie APIs sowie punktuelles Web-Scraping angereichert wird. Ziel ist eine Decodier-Genauigkeit nahe 100 %, mit klarem Schwerpunkt auf europäischen (und türkischen) Fahrzeugen – ein Bereich, den die üblichen kostenlosen US-Quellen nur unvollständig abdecken. Der US-Markt/NHTSA-Daten bleiben als sekundäre, ergänzende Quelle erhalten, sind aber nicht das primäre Ziel. Das Tool verarbeitet ausschließlich technische Fahrzeugdaten (Hersteller, Modell, Baujahr, Technik) – **keinerlei personenbezogene oder Halterdaten**. Das System kombiniert mehrere Datenquellen und liefert das Ergebnis mit einer Konfidenzangabe statt einer reinen Einzelantwort. Start als privates Projekt auf eigener Proxmox-Infrastruktur (ukm.net.tr), mit Option auf spätere Nutzung als Freelance-Produkt und/oder internes KGM-Tool.

---

## 1. Ausgangslage & Herausforderung

Ein VIN (Vehicle Identification Number) besteht aus 17 Zeichen nach ISO 3779/3780: WMI (Herstellerkennung, Position 1–3), VDS (Fahrzeugbeschreibung, 4–9, inkl. Prüfziffer bei US-Fahrzeugen) und VIS (Seriennummer, 10–17, Position 10 = Modelljahr). Die Struktur ist weltweit genormt, aber die Bedeutung der VDS-Zeichen ist herstellerspezifisch und **nicht** standardisiert – das ist der eigentliche Grund, warum ein guter Decoder viele Datenquellen braucht.

Die kostenlose NHTSA-vPIC-API (vpic.nhtsa.dot.gov) ist die mit Abstand umfangreichste freie Quelle (140+ Felder, Bulk-Downloads, keine Rate-Limit-Hürden), deckt aber primär den nordamerikanischen Markt ab. Europäische/türkische Modelle, die nie in die USA verkauft wurden, fehlen dort oder sind unvollständig. Genau dieser Fokus (Europa & Türkei) ist laut deiner Angabe der wichtigste Genauigkeitstreiber – deshalb braucht das Projekt zusätzliche, komplementäre Quellen.

## 2. Zieldefinition

- Öffentliche Weboberfläche zur VIN-Eingabe mit sofortiger Decodierung (Hersteller, Modell, Baujahr, Motor, Ausstattung, Werk) – **kein** Rückruf-/Sicherheitsdaten-Modul, reiner technischer Decoder
- Sprachen: Deutsch, Englisch, Türkisch (vollständige UI-Übersetzung, nicht nur Labels)
- Eigene PostgreSQL-Datenbank als "Source of Truth", befüllt aus mehreren Quellen
- Multi-Source-Abgleich mit Konfidenz-/Herkunftsangabe pro Ergebnis statt Blackbox-Antwort
- Erweiterbare Architektur, damit später weitere Quellen oder Regionen ergänzt werden können
- Ausschließlich freie/kostenlose Datenquellen in der ersten Ausbaustufe (laut deiner Vorgabe)
- Primärer Marktfokus: Europa (inkl. Türkei); US-Markt/NHTSA-Daten nur als sekundäre Ergänzung
- Strikt nur technische Fahrzeugdaten – keine personenbezogenen Daten oder Halterinformationen, weder gespeichert noch angezeigt

## 3. Architekturüberblick

```
[GitHub-Datensätze] ─┐
[NHTSA vPIC Bulk/API] ─┼─▶ ETL-Pipeline (Python) ─▶ PostgreSQL ("vindb")
[Scraping-Quellen] ───┘                                   │
                                                            ▼
                                          Backend-API (FastAPI/Node) mit
                                          Entscheidungslogik + Konfidenz-Score
                                                            │
                                                            ▼
                                     Web-Frontend (Next.js, i18n EN/DE/TR)
```

**Datenbank-Kern (vereinfachtes Schema):**

- `wmi` – Herstellerkennung, Land, Hersteller, Quelle
- `manufacturer_patterns` – herstellerspezifische VDS-Decodierregeln (Position, Bedeutung, Wertebereich)
- `vehicles_reference` – bekannte VIN-Beispiele/Modelle aus importierten Datensätzen
- `lookups_log` – jede Anfrage inkl. genutzter Quelle(n) und Konfidenz (auch für spätere Qualitätsauswertung)
- `sources` – Metadaten zu jeder Datenquelle (Lizenz, Aktualität, Verlässlichkeit)

**Auflösungslogik pro Anfrage:** 1) strukturelle Decodierung (WMI/VDS/VIS, funktioniert immer, deterministisch) → 2) Abgleich gegen eigene DB → 3) bei Lücken/Unsicherheit Live-Nachfrage bei freier API (z. B. NHTSA) → 4) Ergebnis mit Quellenangabe + Konfidenz zusammenführen, Widersprüche zwischen Quellen sichtbar kennzeichnen statt stillschweigend zu wählen.

## 4. Datenquellen-Strategie

**A) Import aus GitHub (einmalig + periodisch aktualisiert):**

- [`idlesign/vininfo`](https://github.com/idlesign/vininfo) – Python-Bibliothek mit herstellerspezifischen Decodier-Regeln, guter Ausgangspunkt für `manufacturer_patterns`
- [`WALL-E/vin-decoder`](https://github.com/WALL-E/vin-decoder) – enthält u. a. eine aus GitHub aggregierte WMI-CSV-Liste
- [`davidpeckham/vin`](https://github.com/davidpeckham/vin) und [`cardog-ai/corgi`](https://github.com/cardog-ai/corgi) – Letzteres nutzt eine angepasste/bereinigte vPIC-Datenbank als TypeScript-Bibliothek, gute Referenz für Datenmodell und Cleaning-Ansatz
- [`adaptant-labs/vin-decoder-dart`](https://github.com/adaptant-labs/vin-decoder-dart), [`louisevanderlith/vin`](https://github.com/louisevanderlith/vin) – weitere Implementierungen zum Quervergleich der Regeln
- Diese Repos unterscheiden sich in Lizenz und Aktualität – jede Quelle wird vor dem Import auf Lizenz geprüft und in `sources` dokumentiert

**B) Freie APIs (laufende Anreicherung):**

- **Priorität 1 – Europa/Türkei:** Kostenlose Optionen für rein technische EU-Fahrzeugdaten sind rar und meist limitiert (Freemium-Kontingente einzelner Anbieter wie vindecoder.eu, Vincario, VehicleDatabases). Da Budget aktuell nur freie Quellen vorsieht, liegt der Schwerpunkt in Phase 1 auf dem GitHub-Import (Abschnitt A) und strukturell hergeleiteter Decodierung (WMI/VDS-Muster); kostenpflichtige EU-APIs werden nur als vorgemerkter Ausbauschritt (Phase 6) dokumentiert, falls sich die Budget-Entscheidung später ändert
- **Priorität 2 – sekundär, USA:** **NHTSA vPIC** (`vpic.nhtsa.dot.gov/api`) – kostenlos, keine Registrierung, Bulk-Download der Gesamtdatenbank möglich; dient als sekundäre Referenz-/Validierungsquelle (auch viele international verkaufte Modelle sind dort gelistet), ist aber nicht die primäre Quelle für rein europäische Modelle
- Bereits existierende **VIN-MCP-Server** (z. B. `mcp.vin`, Apify-VIN-Decoder-MCP) liefern u. a. strukturierte vPIC-Technikdaten – als Referenzimplementierung für die Decoder-Logik nutzbar (nicht für Rückrufe/Sicherheitsdaten, die bewusst außen vor bleiben)
- **Zusätzliche freie Technik-Kataloge (nicht VIN-basiert, aber gut zum Anreichern/Validieren von Modell-/Ausstattungsdaten):** [`plowman/open-vehicle-db`](https://github.com/plowman/open-vehicle-db) (offene Marke/Modell/Baujahr-Datenbank) und ggf. Freemium-Kontingente von [CarAPI](https://carapi.app/) – Lizenz/Umfang vor Einsatz prüfen

**C) Web-Scraping (ergänzend, mit Sorgfalt):**

- Nur für öffentlich zugängliche, strukturierte Hersteller- oder Fachdatenbankseiten mit rein technischen VIN-/Modellinformationen (keine Recall-Seiten, siehe oben – die entfallen komplett)
- Türkische Behördenportale (z. B. e-Devlet) scheiden für ein öffentliches Tool ohnehin aus, da dort personenbezogene/Halterdaten im Vordergrund stehen

**Geprüft, aber ausgeschlossen – kommerzielle VIN-Decoder-Dienste (vindecoder.eu, Fahrnex, AutoRef.eu, VINOPEN):**

Diese vier Dienste wurden konkret geprüft, ob sich ihre Datenbanken importieren lassen. Ergebnis: **Ein Bulk-Import/Scraping ihrer Datenbank ist bei allen vier nicht vertretbar**, unabhängig vom Budget:

- **AutoRef.eu** und **Fahrnex** verbieten in ihren AGB ausdrücklich automatisierten/massenhaften Zugriff sowie Weiterverkauf/Weitergabe der Daten
- **VINOPEN** blockt automatisierten Zugriff bereits technisch (robots.txt) und richtet sich laut eigener Aussage explizit nur an Werkstätten/Fachhändler als zahlende Geschäftskunden ("NOT suitable for private use")
- **vindecoder.eu** (Vincario) bietet nur ein sehr kleines kostenloses Kontingent (20 Abfragen), alles Weitere ist kostenpflichtig
- Zusätzlich greift bei allen vieren voraussichtlich das **EU-Datenbankschutzrecht** (Richtlinie 96/9/EG, "sui generis"-Recht): Wer erheblich in den Aufbau einer Datenbank investiert hat, ist auch ohne explizites ToS-Verbot vor der Übernahme wesentlicher Teile geschützt

**Was stattdessen möglich ist:** Diese Dienste einzeln und manuell als Referenz nutzen (z. B. um eigene Decodier-Regeln stichprobenartig zu verifizieren), oder – falls das Budget später kostenpflichtige APIs erlaubt – als regulärer zahlender API-Kunde einzelne Live-Abfragen durchführen (das ist der von den Anbietern vorgesehene Nutzungszweck, im Gegensatz zum Massenimport der Gesamtdatenbank).

## 5. Empfohlener Tech-Stack

- **Datenbank:** PostgreSQL (bereits vorgegeben), Schema-Migrationen z. B. mit Alembic oder Flyway
- **ETL/Import:** Python (pandas, httpx) für Scraper, Importer und periodische Sync-Jobs, orchestriert z. B. mit einem einfachen Cron/Prefect-Setup auf Proxmox
- **Backend/API:** FastAPI (Python) – Entscheidung getroffen: gleiche Sprache wie die ETL-Pipeline (ein Ökosystem für Import-Skripte und API-Logik, weniger Kontextwechsel, gute Bibliotheken für Datenverarbeitung/Pattern-Matching)
- **Frontend:** Next.js mit `next-intl` o. ä. für EN/DE/TR, minimalistisches UI (z. B. Tailwind), Server-seitiges Rendering für schnelle, SEO-freundliche Ergebnisseiten
- **Deployment:** Docker-Container pro Dienst (DB, API, Frontend, ETL-Worker) auf einer eigenen Proxmox-VM unter `ukm.net.tr`, analog zu deinen bestehenden Projekten (Graylog, Mailcow, psgmon)
- **Monitoring:** Anbindung an dein bestehendes Monitoring-Stack (Grafana/Prometheus), z. B. für Importlauf-Status und API-Fehlerquote

## 6. Phasenplan

| Phase | Inhalt | Ergebnis |
|---|---|---|
| 0 – Discovery (1 Woche) | Offene Fragen klären (s. u.), Ziel-VIN-Beispielset definieren, Lizenzprüfung der GitHub-Quellen | Freigegebene Quellenliste, Testset mit bekannten VINs (inkl. korrektem Ergebnis) zur späteren Genauigkeitsmessung |
| 1 – Datenmodell & Import (2–3 Wochen) | PostgreSQL-Schema, ETL-Skripte für GitHub-Importe + NHTSA-Bulk-Daten | Befüllte Datenbank, Import reproduzierbar/wiederholbar |
| 2 – Decoder-Engine & Backend-API (2 Wochen) | Auflösungslogik (strukturell → DB → Live-API), Konfidenz-Scoring, REST-API | Funktionierende API mit Testabdeckung |
| 3 – Frontend (2 Wochen) | Next.js-UI, EN/DE/TR-Übersetzung, Design (minimalistisch/professionell) | Nutzbare Weboberfläche |
| 4 – Qualitätssicherung (1–2 Wochen) | Abgleich gegen Testset, manuelle Stichproben für EU/TR-Fahrzeuge, Nachschärfen der Herstellerregeln | Gemessene Trefferquote, dokumentierte Lücken |
| 5 – Deployment & Betrieb | Rollout auf Proxmox, Monitoring, Backup-Strategie für die DB | Produktiv nutzbares Tool |
| 6 – Ausbau (optional, später) | Weitere technische Quellen, ggf. kostenpflichtige EU-APIs, evtl. öffentliches Angebot | Erweiterte Abdeckung/Monetarisierung |

## 7. Einsatz von Skills, Agents und MCP

Für die Umsetzung eignen sich mehrere vorhandene Werkzeuge:

- **`engineering:system-design`** und **`engineering:architecture`** – für die detaillierte API-/Datenmodell-Ausarbeitung in Phase 1–2
- **`engineering:testing-strategy`** – für das Testset/die Genauigkeitsmessung in Phase 4
- **`engineering:code-review`** – laufend bei jedem größeren Codeabschnitt
- **Recherche-Agenten** (z. B. für das gezielte Auswerten weiterer GitHub-Repos oder Datenquellen), wenn die Codebasis wächst
- **MCP:** Bestehende VIN-MCP-Server (z. B. `mcp.vin`) können als Referenz oder sogar als zusätzlicher Baustein in der Live-Abfrage-Kette eingebunden werden, um US-Zusatzdaten (Rückrufe, Sicherheitsbewertungen) ohne eigene Anbindung zu bekommen – ersetzt aber nicht die eigene DB als Kernstück

## 8. Rechtliche Hinweise (kein Rechtsrat)

- Jede importierte GitHub-Quelle hat eine eigene Lizenz (MIT, Apache, teils ohne explizite Lizenz) – vor Übernahme in die eigene DB prüfen und dokumentieren
- Scraping nur im Rahmen der jeweiligen Nutzungsbedingungen; keine Umgehung technischer Schutzmaßnahmen
- Da das Tool bewusst **keine personenbezogenen Daten oder Halterinformationen** verarbeitet, sondern ausschließlich technische Fahrzeugdaten (Hersteller, Modell, Technik), sind KVKK (Türkei) und DSGVO in aller Regel nicht einschlägig. Diese Grenze sollte in der Architektur technisch durchgesetzt werden (kein Feld, keine Quelle mit Halter-/Kennzeichen-/Eigentümerbezug wird je importiert oder verknüpft)

## 9. Bereits geklärt

- **Testset:** Existiert noch nicht → wird in Phase 0 von Grund auf aufgebaut (Sammlung bekannter VINs mit verifiziertem Ergebnis, Schwerpunkt Europa/Türkei)
- **Backend-Sprache:** FastAPI (Python) festgelegt
- **Umfang V1:** Reiner technischer Decoder, keine Rückruf-/Sicherheitsdaten
- **Scraping-Ansatz:** Beschränkt sich auf öffentlich zugängliche, rein technische Quellen (Recall-/Behördenseiten von vornherein ausgeschlossen)
- **Zusatzquellen für EU/TR:** [`plowman/open-vehicle-db`](https://github.com/plowman/open-vehicle-db) und [CarAPI](https://carapi.app/) (Freemium) werden als Zusatzquellen einbezogen, Lizenz/Umfang wird in Phase 0 im Detail geprüft
- **Zeitrahmen:** Kein fixes Zieldatum, Tempo flexibel neben der Haupttätigkeit
- **Scraping-Grenze (fixe Rahmenbedingung, nicht verhandelbar):** Scraping bleibt auf Quellen beschränkt, deren Nutzungsbedingungen und robots.txt das zulassen. Für Quellen, die automatisierten/massenhaften Zugriff oder Weiterverwendung explizit untersagen (z. B. die vier geprüften kommerziellen Dienste aus Abschnitt 4), wird kein Scraping umgesetzt – unabhängig vom Wunsch, das zu umgehen. Das ist eine feste Grenze der Zusammenarbeit, keine offene Frage mehr.

## 10. Offene Punkte – bitte klären

_Aktuell keine offenen Punkte mehr – alle Fragen aus der ersten Version sind geklärt (siehe Abschnitt 9)._

---

## 11. Umsetzungsstand (Stand 2026-09-08)

**Phase 0 – Discovery: abgeschlossen.**

- Lizenzprüfung aller genannten GitHub-Quellen durchgeführt, Ergebnis in [`docs/DATENQUELLEN.md`](docs/DATENQUELLEN.md) und in der Tabelle `sources`. Wichtigste Korrektur gegenüber der Planannahme: **`WALL-E/vin-decoder` und `plowman/open-vehicle-db` haben keine Lizenzdatei** und sind damit nicht importierbar; `louisevanderlith/vin` ist GPL-3.0 und scheidet ebenfalls aus. Verwertbar sind vPIC (gemeinfrei), `vininfo` (BSD-3), `corgi` (ISC), `davidpeckham/vin` (MIT) und `vin-decoder-dart` (Apache-2.0). Der ETL-Lauf bricht ab, wenn eine Quelle mit `license_ok = false` importiert werden soll – die Prüfung ist im Code durchgesetzt.
- Test-VIN-Set mit 30 Fällen aufgebaut ([`qa/testset.json`](qa/testset.json), Schwerpunkt EU/TR), inklusive Abgleich, was vPIC selbst liefert.
- **Die Kernannahme des Plans ist belegt:** vPIC kennt bei 21 der 30 Testfälle kein Modell, und die WMIs `TMB` (Škoda), `TMA` (Hyundai CZ), `VSS` (SEAT), `VF7` (Citroën) und `SJN` (Nissan UK) fehlen dort ganz. Für die Türkei sind `NM0`, `NMT` und `NLN` vorhanden.

**Phase 1 – Datenmodell & Import: Code fertig, Lauf gegen eine echte Datenbank steht aus.**

- Schema in `db/migrations/` (reines SQL, wiederholbar einspielbar).
- Importer für NHTSA-WMI-Stammdaten und für die vininfo-Regeln. Der vininfo-Importer extrahiert im Probelauf **703 WMI-Zeilen und 4116 Herstellerregeln** (Renault, Nissan, Opel, Lada, Ford Australia), inklusive der modellabhängigen Motorcodes als Mehrpositions-Muster.
- Noch nicht erfolgt: der Import gegen eine laufende PostgreSQL-Instanz – auf diesem Rechner ist weder Docker noch ein Postgres-Server vorhanden. Das ist der erste Schritt auf der Proxmox-VM.

**Phase 2 – Decoder-Engine & API: abgeschlossen.**

- Strukturelle Decodierung, Multi-Source-Merge (Noisy-OR), Konfidenz-Scoring, sichtbare Widersprüche, Live-Fallback nur bei Lücken.
- FastAPI mit `/api/v1/decode`, `/sources`, `/stats`, `/attributes`, `/health`; 73 Tests, laufen offline.

**Phase 3 – Frontend: abgeschlossen.**

- Next.js 14 mit vollständiger EN/DE/TR-Übersetzung (auch der Hinweistexte, nicht nur der Labels), Konfidenzanzeige pro Feld, Quellenangabe, ISO-3779-Aufschlüsselung.

**Phase 4 – Qualitätssicherung: Messinstrument steht, Ausgangswert gemessen.**

`scripts/accuracy_report.py` misst gegen das Testset. Ohne befüllte Datenbank (nur Struktur + Live-vPIC): Land 100 %, Modelljahr 100 %, Marke 90 %, **Modell 47 %**. Der Wert für Modell ist die Kennzahl, an der sich der Nutzen der eigenen Datenbank messen lassen wird.

**Phase 5 – Deployment: vorbereitet, nicht ausgeführt.** `docker-compose.yml` und Dockerfiles für API, ETL und Frontend liegen vor; DB-Port ist bewusst nicht nach außen geöffnet.

### Nächste Schritte

1. Auf der Proxmox-VM `docker compose up -d db api frontend` und `etl.run_import all` – damit ist Phase 1 abgeschlossen.
2. Genauigkeitsbericht mit befüllter Datenbank erneut laufen lassen und mit dem Ausgangswert oben vergleichen.
3. Die Lücken aus Phase 0 gezielt schließen: eigene `manufacturer_patterns`-Regeln für `TMB`, `VSS`, `VF7`, `SJN`, `TMA` sowie für die türkischen Hersteller – das ist genau der Teil, den keine freie Quelle liefert.
4. Erwartungen im Testset, die noch mit `verified: "open"` markiert sind, manuell bestätigen.
