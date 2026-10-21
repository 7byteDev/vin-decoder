-- =====================================================================
-- Verbrauch und Emissionen zu den Typengenehmigungen (ASTRA TARGA).
--
-- Beide Datensaetze haengen am TG-Code, also an type_approvals.approval_number.
-- Sie enthalten je Getriebevariante eine eigene Zeile - ein Fahrzeugtyp hat
-- deshalb typischerweise mehrere Verbrauchs- und Emissionszeilen.
--
-- Statt 28 bzw. 65 Spalten einzeln abzubilden, werden die wichtigsten
-- Kennwerte typisiert (fuer Anzeige und spaetere Auswertung) und die
-- vollstaendige, beschriftete Zeile als JSON abgelegt - wie bei
-- type_approvals.specs.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS type_approval_extras (
    id                 bigserial PRIMARY KEY,
    source_id          integer NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    approval_number    text NOT NULL,
    kind               text NOT NULL CHECK (kind IN ('consumption', 'emissions')),

    -- Unterscheidungsmerkmale der Variante
    fuel_code          text,
    fuel_type          text,
    transmission       text,
    axle_ratio         text,

    -- Verbrauch (NEFZ und WLTP; 0 im Rohdatensatz bedeutet "nicht zutreffend")
    consumption_l100       numeric(5,2),
    co2_g_km               smallint,
    consumption_wltp_l100  numeric(5,2),
    co2_wltp_g_km          smallint,
    electric_kwh100        numeric(5,2),
    electric_range_km      smallint,
    efficiency_category    text,

    -- Emissionen
    emission_code      text,
    exhaust_code       text,
    cylinders          smallint,
    displacement_ccm   integer,
    power_kw           numeric(6,1),

    data               jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_extras_approval ON type_approval_extras (approval_number, kind);
CREATE INDEX IF NOT EXISTS idx_extras_source ON type_approval_extras (source_id);

INSERT INTO schema_migrations (version) VALUES ('006_consumption_emissions')
ON CONFLICT (version) DO NOTHING;

COMMIT;
