BEGIN;

-- Ruecknahme einer zu strengen Bedingung.
--
-- Migration 023 verlangte mindestens zwei Zeichen je Bezeichnung. Damit
-- fielen genau die Faelle heraus, fuer die die Regel urspruenglich
-- gebaut war: "3er-Reihe" wird zu "3", "E-Klasse" zu "e" - beide einen
-- Zeichen lang. Die Zuordnung sank von 82,8 auf 70 Prozent. Ein Zeichen
-- genuegt; die Sortierung nach Trefferlaenge sorgt weiterhin dafuer, dass
-- der genauere Name gewinnt.
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
        )
        SELECT m.brand_slug, m.slug AS model_slug, m.treffer_laenge
        FROM bereiche b
        JOIN LATERAL (
            SELECT al.model_slug AS slug, al.brand_slug,
                   length(al.prefix) + 100 AS treffer_laenge
              FROM catalog_model_alias al
             WHERE al.brand_slug = b.slug
               AND approval_key(t.model) LIKE al.prefix || '%'
            UNION ALL
            SELECT cm.slug, cm.brand_slug, length(teil.wert)
              FROM catalog_models cm
              CROSS JOIN LATERAL (
                  SELECT catalog_base(trim(x)) AS wert
                    FROM unnest(string_to_array(cm.name, '/')) AS x
              ) teil
             WHERE cm.brand_slug = b.slug
               AND teil.wert <> ''
               AND approval_key(t.model) LIKE teil.wert || '%'
        ) m ON true
        ORDER BY m.treffer_laenge DESC
        LIMIT 1
    ) treffer ON true
    ORDER BY t.id, treffer.treffer_laenge DESC;

    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

INSERT INTO schema_migrations (version) VALUES ('024_catalog_short_names')
ON CONFLICT (version) DO NOTHING;

COMMIT;
