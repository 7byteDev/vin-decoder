BEGIN;

-- Die letzte Gruppe offener Modellnamen.
--
--   S/RS bei Audi   "SQ5", "RS 3", "S 3.0 TFSI" gehoeren zur Baureihe
--                   ohne den Buchstaben davor: Q5, A3.
--   21x / 51x       Weitere Nummernkreise des Sprinter.
--   "724 Huracán"   Der Typenschein stellt eine Nummer voran, der Katalog
--                   kennt nur den Namen. Deshalb wird zusaetzlich eine
--                   Fassung ohne fuehrende Ziffern geprueft.
--
-- Nicht aufgenommen: Lastwagen und Busse (Renault Premium/Kerax, Volvo FH,
-- Mercedes O-Reihe, Isuzu N-Serie). Sie stehen nicht im Katalog, weil er
-- Personenwagen und leichte Nutzfahrzeuge fuehrt - dort waere jede
-- Zuordnung erfunden.

INSERT INTO catalog_model_alias (brand_slug, prefix, model_slug) VALUES
    ('audi', 'sq3', 'q3'), ('audi', 'sq5', 'q5'),
    ('audi', 'sq7', 'q7'), ('audi', 'sq8', 'q8'),
    ('audi', 'rsq3', 'q3'), ('audi', 'rsq5', 'q5'),
    ('audi', 'rsq7', 'q7'), ('audi', 'rsq8', 'q8'),
    ('audi', 'rs3', 'a3'), ('audi', 'rs4', 'a4'), ('audi', 'rs5', 'a5'),
    ('audi', 'rs6', 'a6'), ('audi', 'rs7', 'a7'),
    ('audi', 'audirs3', 'a3'), ('audi', 'audirs4', 'a4'),
    ('audi', 'audirs5', 'a5'), ('audi', 'audirs6', 'a6'),
    ('audi', 'audirs7', 'a7'),
    ('audi', 's3', 'a3'), ('audi', 's4', 'a4'), ('audi', 's5', 'a5'),
    ('audi', 's6', 'a6'), ('audi', 's7', 'a7'), ('audi', 's8', 'a8'),
    ('mercedes-benz', '210', 'sprinter'), ('mercedes-benz', '211', 'sprinter'),
    ('mercedes-benz', '212', 'sprinter'), ('mercedes-benz', '213', 'sprinter'),
    ('mercedes-benz', '214', 'sprinter'), ('mercedes-benz', '215', 'sprinter'),
    ('mercedes-benz', '216', 'sprinter'), ('mercedes-benz', '217', 'sprinter'),
    ('mercedes-benz', '218', 'sprinter'), ('mercedes-benz', '219', 'sprinter'),
    ('mercedes-benz', '510', 'sprinter'), ('mercedes-benz', '511', 'sprinter'),
    ('mercedes-benz', '513', 'sprinter'), ('mercedes-benz', '514', 'sprinter'),
    ('mercedes-benz', '515', 'sprinter'), ('mercedes-benz', '516', 'sprinter'),
    ('mercedes-benz', '517', 'sprinter'), ('mercedes-benz', '519', 'sprinter')
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
                   regexp_replace(approval_key(t.model), '^e', '') AS ohne_e,
                   regexp_replace(approval_key(t.model), '^m(?=[0-9])', '')
                       AS ohne_m,
                   regexp_replace(approval_key(t.model), '^[0-9]+', '')
                       AS ohne_zahl
        )
        SELECT m.brand_slug, m.slug AS model_slug, m.treffer_laenge
        FROM bereiche b, schluessel k
        JOIN LATERAL (
            SELECT al.model_slug AS slug, al.brand_slug,
                   length(al.prefix) + 100 AS treffer_laenge
              FROM catalog_model_alias al
             WHERE al.brand_slug = b.slug
               AND k.voll LIKE al.prefix || '%'
            UNION ALL
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
                    OR k.ohne_m LIKE teil.wert || '%'
                    OR (length(k.ohne_zahl) >= 3
                        AND k.ohne_zahl LIKE teil.wert || '%'))
            UNION ALL
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

INSERT INTO schema_migrations (version) VALUES ('026_catalog_variants')
ON CONFLICT (version) DO NOTHING;

COMMIT;
