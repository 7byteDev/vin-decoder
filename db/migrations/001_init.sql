-- =====================================================================
-- VIN-Decoder - Initiales Schema ("vindb")
--
-- Grundregel dieses Schemas (Projektplan Abschnitt 2 & 8):
-- Es existiert bewusst KEIN Feld fuer personenbezogene Daten,
-- Halter-, Kennzeichen- oder Eigentuemerinformationen. Auch die
-- Anfrage-Logs speichern nur den technischen VIN-Teil (Position 1-11),
-- der Seriennummernblock (12-17) wird maskiert.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- sources: Metadaten zu jeder Datenquelle (Lizenz, Verlaesslichkeit)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sources (
    id              serial PRIMARY KEY,
    key             text NOT NULL UNIQUE,           -- 'nhtsa_vpic', 'vininfo', 'structural', ...
    name            text NOT NULL,
    url             text,
    license         text,                           -- SPDX-Kennung oder 'public-domain'
    license_ok      boolean NOT NULL DEFAULT false, -- Import erlaubt? (Phase-0-Pruefung)
    attribution     text,                           -- Pflichtnennung, falls Lizenz sie verlangt
    reliability     numeric(3,2) NOT NULL DEFAULT 0.50
                    CHECK (reliability >= 0 AND reliability <= 1),
    region_focus    text[] NOT NULL DEFAULT '{}',   -- {'EU','TR','US','GLOBAL'}
    last_import_at  timestamptz,
    record_count    integer NOT NULL DEFAULT 0,
    notes           text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- manufacturers: normalisierte Herstellernamen
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS manufacturers (
    id              serial PRIMARY KEY,
    name            text NOT NULL,                  -- offizieller Name
    normalized_name text NOT NULL UNIQUE,           -- upper/trim, fuer Deduplizierung
    common_name     text,                           -- Marke, z. B. 'Volkswagen'
    country         text,
    country_code    char(2),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- wmi: Herstellerkennung (Position 1-3, bei Kleinserien zusaetzlich 12-14)
-- Mehrere Quellen duerfen dieselbe WMI liefern -> Merge in der Engine.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wmi (
    id                serial PRIMARY KEY,
    code              text NOT NULL,                -- 'WVW', 2-stelliges Praefix ('1N') oder 6-stellig (extended)
    manufacturer_id   integer REFERENCES manufacturers(id) ON DELETE SET NULL,
    manufacturer_name text NOT NULL,
    common_name       text,
    country           text,
    country_code      char(2),
    region            text,                         -- 'EU','TR','NA','AS',...
    vehicle_type      text,                         -- 'Passenger Car', 'Truck', ...
    source_id         integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    confidence        numeric(3,2) NOT NULL DEFAULT 0.80,
    valid_from        date,
    valid_to          date,
    raw               jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT wmi_code_len CHECK (char_length(code) BETWEEN 2 AND 6)
);

-- vehicle_type darf NULL sein, soll aber trotzdem eindeutig sein
CREATE UNIQUE INDEX IF NOT EXISTS idx_wmi_unique_per_source
    ON wmi (code, source_id, manufacturer_name, COALESCE(vehicle_type, ''));

CREATE INDEX IF NOT EXISTS idx_wmi_code ON wmi (code);
CREATE INDEX IF NOT EXISTS idx_wmi_country ON wmi (country_code);

-- ---------------------------------------------------------------------
-- manufacturer_patterns: herstellerspezifische VDS-Regeln
-- Genau der Teil, den ISO 3779 NICHT normiert.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS manufacturer_patterns (
    id           bigserial PRIMARY KEY,
    wmi_code     text NOT NULL,                     -- 'WVW' oder '*' = generisch
    attribute    text NOT NULL,                     -- 'model','series','engine','body','plant','fuel',...
    positions    smallint[] NOT NULL,               -- 1-basierte VIN-Positionen, z. B. {7,8}
    match_type   text NOT NULL DEFAULT 'exact'
                 CHECK (match_type IN ('exact', 'regex')),
    pattern      text NOT NULL,                     -- Zeichenfolge oder Regex fuer diese Positionen
    value        text NOT NULL,                     -- decodierter Wert
    value_i18n   jsonb,                             -- {"de": "...", "en": "...", "tr": "..."}
    year_from    smallint,
    year_to      smallint,
    confidence   numeric(3,2) NOT NULL DEFAULT 0.70,
    source_id    integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    raw          jsonb,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT patterns_unique_check CHECK (array_length(positions, 1) > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_patterns_unique
    ON manufacturer_patterns
       (wmi_code, attribute, positions, pattern, source_id, COALESCE(year_from, 0));

CREATE INDEX IF NOT EXISTS idx_patterns_wmi ON manufacturer_patterns (wmi_code, attribute);

-- ---------------------------------------------------------------------
-- vehicles_reference: bekannte VIN-Muster/Modelle aus importierten Datensaetzen
-- vin_prefix = maskiertes VIN-Praefix (max. Position 1-11), NIE eine volle VIN
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS vehicles_reference (
    id                    bigserial PRIMARY KEY,
    vin_prefix            text NOT NULL,
    wmi_code              text,
    make                  text,
    model                 text,
    series                text,
    trim                  text,
    model_year            smallint,
    body_class            text,
    vehicle_type          text,
    fuel_type             text,
    engine_displacement_l numeric(4,1),
    engine_cylinders      smallint,
    engine_power_kw       smallint,
    drive_type            text,
    transmission          text,
    plant_country         text,
    plant_city            text,
    plant_company         text,
    source_id             integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    confidence            numeric(3,2) NOT NULL DEFAULT 0.60,
    raw                   jsonb,
    created_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vehicles_reference_prefix_len CHECK (char_length(vin_prefix) BETWEEN 3 AND 11)
);

CREATE INDEX IF NOT EXISTS idx_vehref_prefix ON vehicles_reference (vin_prefix);
CREATE INDEX IF NOT EXISTS idx_vehref_wmi_year ON vehicles_reference (wmi_code, model_year);

-- ---------------------------------------------------------------------
-- lookups_log: Anfragen inkl. Quellen und Konfidenz (Qualitaetsauswertung)
-- Bewusst OHNE volle VIN, ohne IP, ohne Nutzerbezug.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lookups_log (
    id                 bigserial PRIMARY KEY,
    requested_at       timestamptz NOT NULL DEFAULT now(),
    vin_masked         text NOT NULL,                -- Position 1-11 + 'XXXXXX'
    wmi_code           text,
    model_year         smallint,
    status             text NOT NULL,                -- 'ok','invalid_vin','partial','error'
    overall_confidence numeric(3,2),
    sources_used       text[] NOT NULL DEFAULT '{}',
    conflicts          jsonb,
    duration_ms        integer,
    lang               char(2),
    -- technische Absicherung: eine vollstaendige VIN darf hier nicht landen
    CONSTRAINT lookups_log_masked CHECK (vin_masked !~ '^[A-HJ-NPR-Z0-9]{17}$')
);

CREATE INDEX IF NOT EXISTS idx_lookups_requested ON lookups_log (requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_lookups_wmi ON lookups_log (wmi_code);

-- ---------------------------------------------------------------------
-- updated_at-Trigger
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $fn$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DO $do$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['sources', 'manufacturers', 'wmi'] LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_%1$s_updated_at ON %1$s;', t);
        EXECUTE format(
            'CREATE TRIGGER trg_%1$s_updated_at BEFORE UPDATE ON %1$s
             FOR EACH ROW EXECUTE FUNCTION set_updated_at();', t);
    END LOOP;
END
$do$;

INSERT INTO schema_migrations (version) VALUES ('001_init')
ON CONFLICT (version) DO NOTHING;

COMMIT;
