BEGIN;

-- Zuordnung der Typengenehmigungen zum Fahrzeugkatalog.
--
-- Der Katalog liefert die Gliederung (Marke > Modell > Baureihe), unsere
-- Typengenehmigungen liefern die technischen Daten. Verbunden werden sie
-- ueber drei Merkmale:
--
--   Marke    ueber brand_catalog (unsere Schreibweise -> Katalog-Adresse)
--   Modell   ueber den Namen: der Modelltext des Typenscheins beginnt mit
--            dem Modellnamen des Katalogs ("Q4 e-tron 40" -> "Q4 e-tron").
--            Gewinnt der laengste Treffer, damit "Q4 e-tron" gegenueber
--            "Q4" bevorzugt wird.
--   Baureihe ueber das Baujahr: die Generation, deren Zeitraum das
--            Modelljahr enthaelt; bei Ueberschneidung die spaetere.
--
-- Was sich nicht eindeutig zuordnen laesst, bleibt draussen. Die Zahl der
-- nicht zugeordneten Genehmigungen ist messbar und gehoert in den Bericht.
CREATE TABLE IF NOT EXISTS approval_catalog (
    approval_id     bigint PRIMARY KEY
                    REFERENCES type_approvals(id) ON DELETE CASCADE,
    brand_slug      text NOT NULL,
    model_slug      text NOT NULL,
    generation_slug text
);

CREATE INDEX IF NOT EXISTS approval_catalog_model_idx
    ON approval_catalog (brand_slug, model_slug, generation_slug);

-- Vergleichsform eines Namens: Kleinbuchstaben, nur Buchstaben und Ziffern.
-- "Q4 e-tron 40" und "q4-e-tron" werden so vergleichbar.
CREATE OR REPLACE FUNCTION catalog_key(text)
RETURNS text LANGUAGE sql IMMUTABLE AS
$$ SELECT lower(regexp_replace(coalesce($1, ''), '[^A-Za-z0-9]', '', 'g')) $$;

CREATE OR REPLACE FUNCTION refresh_catalog_mapping()
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    n integer;
BEGIN
    TRUNCATE approval_catalog;

    INSERT INTO approval_catalog (approval_id, brand_slug, model_slug,
                                  generation_slug)
    SELECT DISTINCT ON (t.id)
           t.id, c.slug, m.slug,
           (SELECT g.slug
              FROM catalog_generations g
             WHERE g.brand_slug = m.brand_slug
               AND g.model_slug = m.slug
               AND t.model_year_from IS NOT NULL
               AND t.model_year_from >= g.year_from
               AND t.model_year_from <= coalesce(g.year_to, 2100)
             ORDER BY g.year_from DESC
             LIMIT 1)
    FROM type_approvals t
    JOIN brand_catalog c ON c.make = t.make
    JOIN catalog_models m ON m.brand_slug = c.slug
     AND catalog_key(t.model) LIKE catalog_key(m.name) || '%'
     AND catalog_key(m.name) <> ''
    ORDER BY t.id, length(catalog_key(m.name)) DESC;

    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;

INSERT INTO schema_migrations (version) VALUES ('020_catalog_mapping')
ON CONFLICT (version) DO NOTHING;

COMMIT;
