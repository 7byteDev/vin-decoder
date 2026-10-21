BEGIN;

-- Letzte Regelgruppe fuer die Zuordnung.
--
-- Vier Muster blieben uebrig, jedes mit eigener Ursache:
--
--   MINI          Der Katalog fuehrt die Baureihe schlicht als "MINI";
--                 der Typenschein nennt die Ausstattung ("Cooper",
--                 "One") oder die Karosserie ("3door", "Cabrio").
--   Mercedes 31x  Dreistellige Zahlen ohne Buchstaben sind Sprinter.
--   e-Berlingo    Die Stromer tragen ein vorangestelltes "e-", der
--                 Katalog fuehrt sie unter dem Namen ohne Vorsilbe.
--   M340i         BMW stellt bei den M-Varianten ein "M" voran; die
--                 Baureihe steht in der Ziffer dahinter.
--   Land Cruiser  Hier ist der Katalogname der laengere ("Land Cruiser
--                 J7/J9/J12/J15/J25"). Deshalb wird auch die umgekehrte
--                 Richtung geprueft - allerdings erst ab vier Zeichen und
--                 mit Abschlag, damit kurze Namen nichts an sich ziehen.

INSERT INTO catalog_model_alias (brand_slug, prefix, model_slug) VALUES
    ('mini', 'cooper', 'mini'),
    ('mini', 'one', 'mini'),
    ('mini', '3door', 'mini'),
    ('mini', '5door', 'mini'),
    ('mini', 'cabrio', 'mini'),
    ('mercedes-benz', '310', 'sprinter'),
    ('mercedes-benz', '311', 'sprinter'),
    ('mercedes-benz', '312', 'sprinter'),
    ('mercedes-benz', '313', 'sprinter'),
    ('mercedes-benz', '314', 'sprinter'),
    ('mercedes-benz', '315', 'sprinter'),
    ('mercedes-benz', '316', 'sprinter'),
    ('mercedes-benz', '317', 'sprinter'),
    ('mercedes-benz', '318', 'sprinter'),
    ('mercedes-benz', '319', 'sprinter')
ON CONFLICT DO NOTHING;

CREATE OR REPLACE FUNCTION refresh_catalog_mapping()
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    n integer;
BEGIN
    TRUNCATE approval_catalog;

    INSERT INTO approval_catalog (approval_id, brand_slug, model_slug,
                                  generation_slug)
    SELECT DISTINCT ON (t.id)
           t.id, treffer.brand_slug, treffer.model_slug,
           (SELECT g.slug
              FROM catalog_generations g
             WHERE g.brand_slug = treffer.brand_slug
               AND g.model_slug = treffer.model_slug
               AND t.model_year_from IS NOT NULL
               AND t.model_year_from >= g.year_from
               AND t.model_year_from <= coalesce(g.year_to, 2100)
             ORDER BY g.year_from DESC
             LIMIT 1)
    FROM type_approvals t
    JOIN LATERAL (
        WITH bereiche AS (
            SELECT c.slug FROM brand_catalog c WHERE c.make = t.make
            UNION
            SELECT a.slug FROM brand_catalog_alias a WHERE a.make = t.make
        ),
        schluessel AS (
            SELECT approval_key(t.model) AS voll,
                   -- ohne die Vorsilbe der Elektroversion
                   regexp_replace(approval_key(t.model), '^e', '') AS ohne_e,
                   -- ohne das vorangestellte M der BMW-Sportvarianten
                   regexp_replace(approval_key(t.model), '^m(?=[0-9])', '') AS ohne_m
        )
        SELECT m.brand_slug, m.slug AS model_slug, m.treffer_laenge
        FROM bereiche b, schluessel k
        JOIN LATERAL (
            -- 1) ausdrueckliche Zuordnung
            SELECT al.model_slug AS slug, al.brand_slug,
                   length(al.prefix) + 100 AS treffer_laenge
              FROM catalog_model_alias al
             WHERE al.brand_slug = b.slug
               AND k.voll LIKE al.prefix || '%'
            UNION ALL
            -- 2) Katalogname (auch jede Bezeichnung eines Sammeleintrags)
            SELECT cm.slug, cm.brand_slug, length(teil.wert)
              FROM catalog_models cm
              CROSS JOIN LATERAL (
                  SELECT catalog_base(trim(x)) AS wert
                    FROM unnest(string_to_array(cm.name, '/')) AS x
              ) teil
             WHERE cm.brand_slug = b.slug
               AND teil.wert <> ''
               AND (k.voll LIKE teil.wert || '%'
                    OR k.ohne_e LIKE teil.wert || '%'
                    OR k.ohne_m LIKE teil.wert || '%')
            UNION ALL
            -- 3) umgekehrte Richtung: der Katalogname ist der laengere
            SELECT cm.slug, cm.brand_slug, length(k.voll) - 2
              FROM catalog_models cm
              CROSS JOIN LATERAL (
                  SELECT catalog_base(trim(x)) AS wert
                    FROM unnest(string_to_array(cm.name, '/')) AS x
              ) teil
             WHERE cm.brand_slug = b.slug
               AND length(k.voll) >= 4
               AND teil.wert LIKE k.voll || '%'
        ) m ON true
        ORDER BY m.treffer_laenge DESC
        LIMIT 1
    ) treffer ON true
    ORDER BY t.id, treffer.treffer_laenge DESC;

    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

INSERT INTO schema_migrations (version) VALUES ('025_catalog_rules')
ON CONFLICT (version) DO NOTHING;

COMMIT;
