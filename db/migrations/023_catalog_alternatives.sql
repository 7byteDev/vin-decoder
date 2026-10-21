BEGIN;

-- Katalognamen mit mehreren Bezeichnungen aufloesen.
--
-- Der Katalog fasst verwandte Karosserien unter einem Eintrag zusammen:
-- "S60/V60", "S40/V40/V50", "S70/V70/XC70", "142/144/145". Ein Typenschein
-- nennt immer nur eine davon ("V60 D3"), weshalb der Vergleich mit dem
-- vollen Eintrag fehlschlug - allein bei Volvo blieben 4 558 Genehmigungen
-- liegen. Jetzt zaehlt jede Bezeichnung fuer sich.
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
            -- 1) ausdrueckliche Zuordnung
            SELECT al.model_slug AS slug, al.brand_slug,
                   length(al.prefix) + 100 AS treffer_laenge
              FROM catalog_model_alias al
             WHERE al.brand_slug = b.slug
               AND approval_key(t.model) LIKE al.prefix || '%'
            UNION ALL
            -- 2) jede Bezeichnung des Katalogeintrags einzeln
            SELECT cm.slug, cm.brand_slug, length(teil.wert)
              FROM catalog_models cm
              CROSS JOIN LATERAL (
                  SELECT catalog_base(trim(x)) AS wert
                    FROM unnest(string_to_array(cm.name, '/')) AS x
              ) teil
             WHERE cm.brand_slug = b.slug
               AND length(teil.wert) >= 2
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

INSERT INTO schema_migrations (version) VALUES ('023_catalog_alternatives')
ON CONFLICT (version) DO NOTHING;

COMMIT;
