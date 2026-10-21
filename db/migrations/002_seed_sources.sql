-- =====================================================================
-- Seed der Quellen-Registry inkl. Ergebnis der Phase-0-Lizenzpruefung.
-- license_ok = false bedeutet: NICHT importieren, hoechstens manuell
-- als Referenz vergleichen. Siehe docs/DATENQUELLEN.md.
-- =====================================================================

BEGIN;

INSERT INTO sources (key, name, url, license, license_ok, attribution, reliability, region_focus, notes) VALUES
('structural',
 'Strukturelle Decodierung (ISO 3779 / ISO 3780)',
 NULL, 'n/a', true, NULL, 0.95, ARRAY['GLOBAL'],
 'Deterministische Herleitung aus dem VIN-Aufbau selbst: Region/Land, WMI-Split, Pruefziffer, Modelljahr-Code, Werkscode, Seriennummer. Keine externe Datenquelle.'),

('nhtsa_vpic',
 'NHTSA vPIC (US Department of Transportation)',
 'https://vpic.nhtsa.dot.gov/api', 'public-domain', true,
 'U.S. National Highway Traffic Safety Administration, vPIC',
 0.85, ARRAY['US','GLOBAL'],
 'Werk der US-Bundesregierung, gemeinfrei. Umfangreichste freie Quelle; enthaelt auch viele europaeische WMIs inkl. Laenderzuordnung. Sekundaerquelle laut Projektplan: fuer rein europaeische Modelle unvollstaendig.'),

('vininfo',
 'idlesign/vininfo',
 'https://github.com/idlesign/vininfo', 'BSD-3-Clause', true,
 'vininfo, (c) Igor Starikov (idlesign), BSD-3-Clause',
 0.80, ARRAY['EU','GLOBAL'],
 'Python-Bibliothek mit herstellerspezifischen VDS-Regeln (u. a. AvtoVAZ, Nissan, Opel, Renault). Basis fuer manufacturer_patterns. BSD-3-Clause verlangt Namensnennung.'),

('corgi',
 'cardog-ai/corgi',
 'https://github.com/cardog-ai/corgi', 'ISC', true,
 'corgi, cardog-ai, ISC License',
 0.70, ARRAY['US','GLOBAL'],
 'Bereinigte/kompaktierte vPIC-Datenbank als TS-Bibliothek. Nuetzlich als Referenz fuer Datenmodell und Cleaning; inhaltlich vPIC-abgeleitet, daher nicht unabhaengig.'),

('davidpeckham_vin',
 'davidpeckham/vin',
 'https://github.com/davidpeckham/vin', 'MIT', true,
 'davidpeckham/vin, MIT License',
 0.65, ARRAY['US'],
 'Python-Decoder mit vPIC-Auszug. Vor allem US-Fahrzeuge.'),

('vin_decoder_dart',
 'adaptant-labs/vin-decoder-dart',
 'https://github.com/adaptant-labs/vin-decoder-dart', 'Apache-2.0', true,
 'adaptant-labs/vin-decoder-dart, Apache License 2.0',
 0.60, ARRAY['EU','GLOBAL'],
 'Dart-Implementierung, dient dem Quervergleich der Regeln (WMI-Land-Ranges, Jahrescodes).'),

-- --------------------- geprueft, aber NICHT importierbar ---------------------
('wall_e_vin_decoder',
 'WALL-E/vin-decoder',
 'https://github.com/WALL-E/vin-decoder', 'NOASSERTION', false, NULL,
 0.40, ARRAY['GLOBAL'],
 'PHASE-0-ERGEBNIS: Repository hat keine Lizenzdatei -> standardmaessig alle Rechte vorbehalten. Die WMI-CSVs werden NICHT importiert. Nur manueller Stichprobenvergleich.'),

('open_vehicle_db',
 'plowman/open-vehicle-db',
 'https://github.com/plowman/open-vehicle-db', 'NOASSERTION', false, NULL,
 0.40, ARRAY['US','GLOBAL'],
 'PHASE-0-ERGEBNIS: keine Lizenzdatei im Repository -> kein Import. Ersatz fuer Marke/Modell/Baujahr: vPIC (gemeinfrei).'),

('louisevanderlith_vin',
 'louisevanderlith/vin',
 'https://github.com/louisevanderlith/vin', 'GPL-3.0', false, NULL,
 0.50, ARRAY['GLOBAL'],
 'PHASE-0-ERGEBNIS: GPL-3.0 (starkes Copyleft). Uebernahme von Daten/Code wuerde das Projekt binden -> nicht importiert, nur als Referenz gelesen.'),

('carapi',
 'CarAPI (Freemium)',
 'https://carapi.app/', 'proprietary-freemium', false, NULL,
 0.60, ARRAY['US','EU'],
 'Freemium-Kontingent, Bulk-Uebernahme laut AGB nicht zulaessig. Erst in Phase 6 als bezahlte Live-Quelle relevant.'),

('manual_review',
 'Manuelle Verifikation / Stichprobe',
 NULL, 'n/a', true, NULL, 0.98, ARRAY['EU','TR'],
 'Von Hand geprüfte und bestaetigte Regeln oder WMIs (Phase 4). Hoechste Verlaesslichkeit, kleinste Abdeckung.')

ON CONFLICT (key) DO UPDATE SET
    name = EXCLUDED.name,
    url = EXCLUDED.url,
    license = EXCLUDED.license,
    license_ok = EXCLUDED.license_ok,
    attribution = EXCLUDED.attribution,
    reliability = EXCLUDED.reliability,
    region_focus = EXCLUDED.region_focus,
    notes = EXCLUDED.notes;

INSERT INTO schema_migrations (version) VALUES ('002_seed_sources')
ON CONFLICT (version) DO NOTHING;

COMMIT;
