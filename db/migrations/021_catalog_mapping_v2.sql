BEGIN;

-- Zuordnung Typengenehmigung -> Katalog, zweiter Anlauf.
--
-- Der erste Versuch verglich die Namen als reine Zeichenkette von vorn.
-- Damit blieben 58 000 Genehmigungen unzugeordnet, aus drei Gruenden:
--
--   1. Der Typenschein schiebt die Leistungsangabe in die Mitte:
--      "Q4 40 e-tron" gegen "Q4 e-tron" im Katalog.
--   2. Der Katalog haengt eine Gattungsbezeichnung an: "E-Klasse",
--      "3er-Reihe" - im Typenschein steht "E 220 d" bzw. "320d".
--   3. Nutzfahrzeuge stehen unter einer eigenen Katalogmarke: der VW T6
--      liegt unter "vw-nutzfahrzeuge/transporter".
--
-- Dagegen hilft: Zahlen aus dem Modelltext entfernen, die Gattung vom
-- Katalognamen abschneiden, und zwei kleine Zuordnungstabellen fuer die
-- Faelle, die sich nicht rechnen lassen.

-- Zusaetzliche Katalogbereiche einer Marke.
CREATE TABLE IF NOT EXISTS brand_catalog_alias (
    make text NOT NULL,
    slug text NOT NULL,
    PRIMARY KEY (make, slug)
);

INSERT INTO brand_catalog_alias (make, slug) VALUES
    ('VW', 'vw-nutzfahrzeuge'),
    ('VW NUTZFAHRZEUGE', 'vw'),
    ('MERCEDES-AMG', 'mercedes-benz')
ON CONFLICT DO NOTHING;

-- Modellnamen, die sich nicht aus dem Text ableiten lassen.
CREATE TABLE IF NOT EXISTS catalog_model_alias (
    brand_slug text NOT NULL,
    prefix     text NOT NULL,   -- Vergleichsform des Modelltexts
    model_slug text NOT NULL,
    PRIMARY KEY (brand_slug, prefix)
);

INSERT INTO catalog_model_alias (brand_slug, prefix, model_slug) VALUES
    -- Die Transportergenerationen heissen im Katalog alle "Transporter".
    ('vw-nutzfahrzeuge', 't4', 'transporter'),
    ('vw-nutzfahrzeuge', 't5', 'transporter'),
    ('vw-nutzfahrzeuge', 't6', 'transporter'),
    ('vw-nutzfahrzeuge', 't7', 'transporter'),
    ('vw-nutzfahrzeuge', 'caravelle', 'transporter'),
    ('vw-nutzfahrzeuge', 'multivan', 'transporter'),
    ('vw-nutzfahrzeuge', 'california', 'transporter'),
    ('land-rover', 'rr', 'range-rover'),
    ('land-rover', 'rrs', 'range-rover-sport'),
    ('land-rover', 'rre', 'range-rover-evoque'),
    ('land-rover', 'rrv', 'range-rover-velar')
ON CONFLICT DO NOTHING;

-- Vergleichsform des Modelltexts: ohne freistehende Zahlen und ohne die
-- ueblichen Karosseriekuerzel. "Q4 40 e-tron qu" wird zu "q4etron".
CREATE OR REPLACE FUNCTION approval_key(text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT lower(regexp_replace(
        regexp_replace(
            regexp_replace(coalesce($1, ''), '\y\d+\y', ' ', 'g'),
            '\y(qu|quattro|sb|av|avant|sw|sportback|coupe|cabrio|4m|4matic|xdrive|allrad)\y',
            ' ', 'gi'),
        '[^A-Za-z0-9]', '', 'g'))
$$;

-- Vergleichsform des Katalognamens ohne Gattungsbezeichnung:
-- "E-Klasse" -> "e", "3er-Reihe" -> "3", "Q4 e-tron" -> "q4etron".
CREATE OR REPLACE FUNCTION catalog_base(text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT lower(regexp_replace(
        regexp_replace(coalesce($1, ''), '(-|\s)?(klasse|reihe)$', '', 'i'),
        '[^A-Za-z0-9]', '', 'g'))
$$;

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
        -- Alle Katalogbereiche dieser Marke
        WITH bereiche AS (
            SELECT c.slug FROM brand_catalog c WHERE c.make = t.make
            UNION
            SELECT a.slug FROM brand_catalog_alias a WHERE a.make = t.make
        )
        -- 1) ausdrueckliche Zuordnung, 2) voller Name, 3) Name ohne Gattung
        SELECT m.brand_slug, m.slug AS model_slug, treffer_laenge
        FROM bereiche b
        JOIN LATERAL (
            SELECT al.model_slug AS slug, al.brand_slug,
                   length(al.prefix) + 100 AS treffer_laenge
              FROM catalog_model_alias al
             WHERE al.brand_slug = b.slug
               AND approval_key(t.model) LIKE al.prefix || '%'
            UNION ALL
            SELECT cm.slug, cm.brand_slug,
                   length(catalog_base(cm.name)) AS treffer_laenge
              FROM catalog_models cm
             WHERE cm.brand_slug = b.slug
               AND catalog_base(cm.name) <> ''
               AND (approval_key(t.model) LIKE catalog_base(cm.name) || '%'
                    OR approval_key(t.model) = catalog_base(cm.name))
        ) m ON true
        ORDER BY treffer_laenge DESC
        LIMIT 1
    ) treffer ON true
    ORDER BY t.id, treffer.treffer_laenge DESC;

    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

INSERT INTO schema_migrations (version) VALUES ('021_catalog_mapping_v2')
ON CONFLICT (version) DO NOTHING;

COMMIT;
