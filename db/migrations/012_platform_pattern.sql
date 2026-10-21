-- =====================================================================
-- Plattformcode robuster erkennen.
--
-- Die erste Fassung erwartete "^[A-Z0-9]{1,6};" - zu eng. TARGA trennt
-- den Code je nach Hersteller unterschiedlich ab:
--
--     B8; ACLABF1/...        Audi        Semikolon
--     906AC35; K?M21...      Mercedes    sieben Zeichen
--     MB: MB1M9TM1A33...     Renault     Doppelpunkt
--     P-J; ...               Opel        Bindestrich im Code
--     1J      Motor: BEH...  VW          nur Leerzeichen
--
-- Dadurch fehlten ganze Marken in model_generations - und ohne
-- Generation landeten auf der Detailseite Bilder der falschen Baureihe
-- (ein Astra F bei einem Astra J).
-- =====================================================================

BEGIN;

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
               substring(variant from '^\s*([A-Z0-9][A-Z0-9-]{0,7})\s*(?:[;:]|\s\s|$)')
                   AS platform,
               min(model_year_from) AS year_from,
               max(model_year_from) AS year_to,
               count(*) AS approvals
        FROM type_approvals
        WHERE make IS NOT NULL
          AND model IS NOT NULL AND model <> ''
          AND variant ~ '^\s*[A-Z0-9][A-Z0-9-]{0,7}\s*([;:]|\s\s|$)'
          AND model_year_from IS NOT NULL
        GROUP BY 1, 2, 3
        HAVING count(*) >= 5
    ) g
    WHERE platform IS NOT NULL AND platform <> '';

    GET DIAGNOSTICS written = ROW_COUNT;
    RETURN written;
END;
$fn$ LANGUAGE plpgsql;

SELECT refresh_model_generations();

INSERT INTO schema_migrations (version) VALUES ('012_platform_pattern')
ON CONFLICT (version) DO NOTHING;

COMMIT;
