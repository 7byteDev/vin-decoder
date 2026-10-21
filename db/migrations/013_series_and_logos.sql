-- =====================================================================
-- Zwei Ergaenzungen:
--
-- 1. Baureihe aus dem VIN-Muster
--
--    Bei Marken wie Mercedes-Benz besteht der Modellname aus einem
--    einzelnen Buchstaben ("S 400 d 4m") - als Suchbegriff wertlos. Die
--    Baureihe steht aber im VIN-Muster:
--
--        W1K223.33........  ->  223  ->  "Mercedes-Benz W223"
--
--    Genau danach benennt Wikimedia die Dateien
--    ("MERCEDES-BENZ S-CLASS (W223) ..."), waehrend eine Suche nach
--    "Mercedes-Benz S" nichts Brauchbares findet.
--
-- 2. Markenlogos
--
--    Wikidata fuehrt zu jeder Marke ein Logo (Eigenschaft P154), das auf
--    Wikimedia Commons liegt. Gespeichert werden nur Dateiname und
--    Lizenzangabe; das Bild selbst bleibt bei Wikimedia.
-- =====================================================================

BEGIN;

ALTER TABLE model_generations ADD COLUMN IF NOT EXISTS vin_vds text;

CREATE TABLE IF NOT EXISTS brand_logos (
    make         text PRIMARY KEY,
    file_name    text NOT NULL,
    page_url     text,
    license      text,
    license_url  text,
    author       text,
    width        integer,
    height       integer,
    wikidata_id  text,
    imported_at  timestamptz NOT NULL DEFAULT now()
);

-- Auch die Fehlversuche merken, damit ein Wiederholungslauf nicht
-- dieselbe Marke erneut anfragt.
CREATE TABLE IF NOT EXISTS brand_logo_lookups (
    make        text PRIMARY KEY,
    found       boolean NOT NULL DEFAULT false,
    checked_at  timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION refresh_model_generations() RETURNS integer AS $fn$
DECLARE
    written integer;
BEGIN
    DELETE FROM model_generations;

    INSERT INTO model_generations
        (make, model_family, platform, year_from, year_to, generation_index,
         approvals, vin_vds)
    SELECT make, family, platform, year_from, year_to,
           row_number() OVER (PARTITION BY make, family ORDER BY year_from, platform),
           approvals, vin_vds
    FROM (
        SELECT t.make,
               split_part(t.model, ' ', 1) AS family,
               substring(t.variant from '^\s*([A-Z0-9][A-Z0-9-]{0,7})\s*(?:[;:]|\s\s|$)')
                   AS platform,
               min(t.model_year_from) AS year_from,
               max(t.model_year_from) AS year_to,
               count(*) AS approvals,
               -- Fahrzeugbeschreibung des haeufigsten VIN-Musters
               -- (Position 4-9), fuer die Ableitung der Baureihe
               mode() WITHIN GROUP (ORDER BY substring(p.pattern from 4 for 6)) AS vin_vds
        FROM type_approvals t
        LEFT JOIN type_approval_vin_patterns p ON p.type_approval_id = t.id
        WHERE t.make IS NOT NULL
          AND t.model IS NOT NULL AND t.model <> ''
          AND t.variant ~ '^\s*[A-Z0-9][A-Z0-9-]{0,7}\s*([;:]|\s\s|$)'
          AND t.model_year_from IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING count(*) >= 5
    ) g
    WHERE platform IS NOT NULL AND platform <> '';

    GET DIAGNOSTICS written = ROW_COUNT;
    RETURN written;
END;
$fn$ LANGUAGE plpgsql;

SELECT refresh_model_generations();

INSERT INTO schema_migrations (version) VALUES ('013_series_and_logos')
ON CONFLICT (version) DO NOTHING;

COMMIT;
