-- =====================================================================
-- Fahrzeuggenerationen aus den eigenen Typengenehmigungsdaten.
--
-- Problem: ein Foto der Modellfamilie passt nicht automatisch zum
-- Baujahr. Fuer einen Octavia von 2011 taugt ein Bild der vierten
-- Generation von 2021 nicht.
--
-- Loesung ohne weitere Fremdquelle: TARGA fuehrt im Feld "05 Typ;
-- Variante/Version" den Plattformcode des Herstellers als ersten Token
-- ("B8; ...", "1Z; ...", "8P; ..."). Gruppiert man die Genehmigungen
-- danach, ergibt der Zeitraum ihrer Erteilung genau den Bauzeitraum der
-- Generation:
--
--     AUDI A3  8P  2003-2013
--     AUDI A3  8V  2012-2020
--     AUDI A3  GY  2020-2023
--
-- Damit laesst sich ein Bild auf die richtige Generation eingrenzen.
-- Zusaetzlich wird die Generation durchnummeriert - Commons benennt
-- Dateien haeufig mit roemischen Ziffern ("Octavia II").
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS model_generations (
    id               bigserial PRIMARY KEY,
    make             text NOT NULL,
    model_family     text NOT NULL,
    platform         text NOT NULL,
    year_from        smallint NOT NULL,
    year_to          smallint NOT NULL,
    generation_index smallint NOT NULL,
    approvals        integer NOT NULL,
    refreshed_at     timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_generations_unique
    ON model_generations (make, model_family, platform);
CREATE INDEX IF NOT EXISTS idx_generations_lookup
    ON model_generations (make, model_family, year_from);

-- Neu aufbauen; wird nach jedem TARGA-Import aufgerufen.
CREATE OR REPLACE FUNCTION refresh_model_generations() RETURNS integer AS $fn$
DECLARE
    written integer;
BEGIN
    DELETE FROM model_generations;

    INSERT INTO model_generations
        (make, model_family, platform, year_from, year_to, generation_index, approvals)
    SELECT make, family, platform, year_from, year_to,
           row_number() OVER (PARTITION BY make, family ORDER BY year_from, platform),
           approvals
    FROM (
        SELECT make,
               split_part(model, ' ', 1) AS family,
               substring(variant from '^([A-Z0-9]{1,6});') AS platform,
               min(model_year_from) AS year_from,
               max(model_year_from) AS year_to,
               count(*) AS approvals
        FROM type_approvals
        WHERE make IS NOT NULL
          AND model IS NOT NULL AND model <> ''
          AND variant ~ '^[A-Z0-9]{1,6};'
          AND model_year_from IS NOT NULL
        GROUP BY 1, 2, 3
        -- Einzelfaelle taugen nicht als Generation
        HAVING count(*) >= 5
    ) g;

    GET DIAGNOSTICS written = ROW_COUNT;
    RETURN written;
END;
$fn$ LANGUAGE plpgsql;

SELECT refresh_model_generations();

INSERT INTO schema_migrations (version) VALUES ('010_model_generations')
ON CONFLICT (version) DO NOTHING;

COMMIT;
