BEGIN;

-- Welche unserer Marken im Autokatalog ueberhaupt vorkommen.
--
-- Der Typengenehmigungsbestand fuehrt 704 Marken, darunter Traktoren
-- (John Deere, Claas, Fendt), Aufbauhersteller (Citroen-Dangel) und
-- Einzelanfertigungen. Fuer das Blaettern nach Marke ist das unbrauchbar -
-- dort gehoeren die Fahrzeugmarken hin. Der Bildimporter traegt hier ein,
-- welche Marke er im Katalog gefunden hat.
CREATE TABLE IF NOT EXISTS brand_catalog (
    make       text PRIMARY KEY,
    slug       text NOT NULL,
    models     integer NOT NULL DEFAULT 0,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version) VALUES ('016_brand_catalog')
ON CONFLICT (version) DO NOTHING;

COMMIT;
