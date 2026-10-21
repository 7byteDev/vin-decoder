-- =====================================================================
-- Typengenehmigungen (Schweizer TARGA-Daten des ASTRA, Open Government Data)
--
-- Das ist der Baustein, der die eigentliche Luecke schliesst: die VIN
-- allein sagt nichts ueber Motor, Leistung oder Getriebe eines
-- europaeischen Fahrzeugs. Die Typengenehmigung sagt es - und sie
-- traegt in der Spalte "06 Vorziffer" ein VIN-Muster mit Platzhaltern,
-- ueber das sich beides verbinden laesst:
--
--     VF1RJA...........  ->  Renault Clio, 999 ccm, 67 kW, Benzin
--
-- Ein VIN-Muster trifft in der Regel mehrere Genehmigungen (verschiedene
-- Motorisierungen derselben Baureihe). Genau dafuer ist die Konfidenz-
-- und Alternativenlogik der Engine da.
--
-- Weiterhin gilt: keine personenbezogenen Daten. Der Datensatz enthaelt
-- Fahrzeugtypen, keine Fahrzeuge und keine Halter. Der Feldwert
-- "Typengenehmigungsinhaber" wird vom ASTRA gar nicht erst als OGD
-- veroeffentlicht.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS type_approvals (
    id                  bigserial PRIMARY KEY,
    source_id           integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,

    -- Identifikation
    approval_number     text NOT NULL,          -- Schweizer TG-Nummer, z. B. '1AA101'
    approval_date       date,
    eu_approval_number  text,                   -- z. B. 'e2*2007/46-2020/1181*0676'

    -- Fahrzeug
    make                text,
    model               text,                   -- "04 Typ"
    variant             text,                   -- "05 Typ; Variante/Version"
    manufacturer        text,
    vehicle_kind        text,                   -- Fahrzeugart, z. B. 'Personenwagen'
    vehicle_class       text,                   -- M1, N1, ...
    body_form           text,
    is_offroad          boolean,

    -- Antrieb
    engine_make         text,
    engine_model        text,
    engine_code         text,
    engine_design       text,
    fuel_code           text,                   -- B, D, C, ... (Rohcode)
    fuel_type           text,                   -- aufgeloest: Benzin, Diesel, ...
    displacement_ccm    integer,
    power_kw            numeric(6,1),
    power_rpm           integer,
    torque_nm           integer,
    torque_rpm          integer,
    drive_type          text,
    transmission        text,                   -- erste Getriebevariante, z. B. 'm6'
    gears               smallint,

    -- Karosserie
    doors               smallint,
    seats_total         smallint,
    top_speed_kmh       smallint,

    -- Masse (jeweils der untere Wert des Bereichs)
    length_mm           integer,
    width_mm            integer,
    height_mm           integer,
    wheelbase_mm        integer,
    weight_kg           integer,
    max_weight_kg       integer,

    model_year_from     smallint,               -- aus dem Genehmigungsdatum

    --  Vollstaendiger Datensatz, nach Abschnitten gruppiert; die
    --  Detailseite rendert daraus, das Frontend uebersetzt die Schluessel.
    specs               jsonb NOT NULL DEFAULT '{}'::jsonb,

    confidence          numeric(3,2) NOT NULL DEFAULT 0.90,
    imported_at         timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ta_approval_number ON type_approvals (approval_number);
CREATE INDEX IF NOT EXISTS idx_ta_make_model ON type_approvals (make, model);
CREATE INDEX IF NOT EXISTS idx_ta_source ON type_approvals (source_id);

-- ---------------------------------------------------------------------
-- VIN-Muster je Genehmigung.
--
-- Das Muster ist 17 Zeichen lang, Platzhalter sind Punkte. In aller Regel
-- steht der feste Teil vorn ("VF1RJA..........."), gelegentlich stehen
-- Platzhalter mitten drin - dafuer gibt es zusaetzlich einen Regex.
--
-- Gesucht wird ueber die Spalte prefix mit einer Gleichheitsabfrage auf
-- alle Praefixlaengen der VIN; das nutzt den Index, anders als ein LIKE.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS type_approval_vin_patterns (
    id                bigserial PRIMARY KEY,
    type_approval_id  bigint NOT NULL REFERENCES type_approvals(id) ON DELETE CASCADE,
    pattern           text NOT NULL,            -- Rohmuster, z. B. 'VF1RJA...........'
    prefix            text NOT NULL,            -- fester Anfang, z. B. 'VF1RJA'
    regex             text,                     -- nur bei Platzhaltern in der Mitte
    CONSTRAINT vin_prefix_len CHECK (char_length(prefix) BETWEEN 2 AND 17)
);

CREATE INDEX IF NOT EXISTS idx_tavp_prefix ON type_approval_vin_patterns (prefix);
CREATE INDEX IF NOT EXISTS idx_tavp_approval ON type_approval_vin_patterns (type_approval_id);

-- ---------------------------------------------------------------------
-- Quelle registrieren
-- ---------------------------------------------------------------------
INSERT INTO sources (key, name, url, license, license_ok, attribution, reliability, region_focus, notes)
VALUES (
    'astra_targa',
    'ASTRA TARGA - Schweizer Typengenehmigungen (Open Government Data)',
    'https://opendata.astra.admin.ch/ivzod/2000-Typengenehmigungen_TG_TARGA/',
    'ogd-ch',
    true,
    'Bundesamt fuer Strassen ASTRA, Typengenehmigungsdaten TARGA (Open Government Data)',
    0.92,
    ARRAY['EU','CH'],
    'Technische Angaben und Emissionsdaten aller in der Schweiz typengenehmigten Fahrzeuge. '
    'Woechentliche Aktualisierung (freitags). Enthaelt in "06 Vorziffer" ein VIN-Muster, ueber '
    'das sich Fahrgestellnummer und Technikdaten verbinden lassen - die zentrale Quelle fuer '
    'Motor, Leistung, Getriebe und Abmessungen europaeischer Fahrzeuge. Deckt in der Schweiz '
    'zugelassene Typen ab; rein national vermarktete Modelle (z. B. nur fuer den TR-Markt) '
    'koennen fehlen.'
)
ON CONFLICT (key) DO UPDATE SET
    name = EXCLUDED.name, url = EXCLUDED.url, license = EXCLUDED.license,
    license_ok = EXCLUDED.license_ok, attribution = EXCLUDED.attribution,
    reliability = EXCLUDED.reliability, region_focus = EXCLUDED.region_focus,
    notes = EXCLUDED.notes;

INSERT INTO schema_migrations (version) VALUES ('004_type_approvals')
ON CONFLICT (version) DO NOTHING;

COMMIT;
