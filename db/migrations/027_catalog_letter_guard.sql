BEGIN;

-- Einbuchstabige Vergleichsformen absichern.
--
-- "V-Klasse" wird zu "v", "E-Klasse" zu "e". Das ist gewollt, damit
-- "E 220 d" seine Baureihe findet - aber es zog auch alles an sich, was
-- zufaellig mit demselben Buchstaben beginnt: der Lastwagen "Vario"
-- landete unter der V-Klasse.
--
-- Ein einzelner Buchstabe zaehlt deshalb nur noch, wenn er im Modelltext
-- allein steht ("E 220 d", "S 350"), nicht als Wortanfang ("Vario").
-- Ziffern bleiben unberuehrt: "320d" soll weiterhin zur 3er-Reihe finden.
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
                       AS ohne_zahl,
                   catalog_ascii(t.model) AS klartext
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
               -- Ein einzelner Buchstabe muss im Modelltext allein stehen
               AND (length(teil.wert) > 1
                    OR teil.wert ~ '[0-9]'
                    OR k.klartext ~* ('^' || teil.wert || '([^A-Za-z]|$)'))
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

-- Beschriftung der Generationen lesbar machen: der Katalog nummeriert sie
-- im Adressteil ("1generation"), daraus wurde beim Import "1GENERATION".
UPDATE catalog_generations
   SET name = regexp_replace(name, '^([0-9]+)GENERATION', '\1. Generation')
 WHERE name ~ '^[0-9]+GENERATION';

INSERT INTO schema_migrations (version) VALUES ('027_catalog_letter_guard')
ON CONFLICT (version) DO NOTHING;

COMMIT;
