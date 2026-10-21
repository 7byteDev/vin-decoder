BEGIN;

-- Der Fahrzeugkatalog als eigene Ebene.
--
-- Bisher wurde die Markenuebersicht aus unseren Typengenehmigungen
-- abgeleitet: Modellname = erstes Wort des Modellfelds, Generation = ein
-- Plattformcode aus dem Variantenfeld. Beides ist eine Naeherung und geht
-- schief. "Q4 e-tron" landete unter "Q4", "e-tron GT" unter "e-tron", und
-- Modelle ohne erkennbaren Plattformcode verschwanden ganz - bei Audi
-- fehlten so vier von 42 Baureihen.
--
-- Deshalb bekommt die Navigation eine eigene Grundlage: den Katalog, so
-- wie er gegliedert ist. Die Typengenehmigungen haengen darunter und
-- liefern weiterhin die technischen Daten.
CREATE TABLE IF NOT EXISTS catalog_brands (
    slug        text PRIMARY KEY,
    name        text NOT NULL,
    logo        bytea,
    logo_thumb  bytea,
    models      integer NOT NULL DEFAULT 0,
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS catalog_models (
    brand_slug  text NOT NULL REFERENCES catalog_brands(slug) ON DELETE CASCADE,
    slug        text NOT NULL,
    name        text NOT NULL,
    generations integer NOT NULL DEFAULT 0,
    image       bytea,
    thumb       bytea,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_slug, slug)
);

CREATE TABLE IF NOT EXISTS catalog_generations (
    brand_slug  text NOT NULL,
    model_slug  text NOT NULL,
    slug        text NOT NULL,
    name        text NOT NULL,
    year_from   integer,
    year_to     integer,
    image       bytea,
    thumb       bytea,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_slug, model_slug, slug),
    FOREIGN KEY (brand_slug, model_slug)
        REFERENCES catalog_models(brand_slug, slug) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS catalog_models_brand_idx
    ON catalog_models (brand_slug, name);

INSERT INTO schema_migrations (version) VALUES ('019_catalog')
ON CONFLICT (version) DO NOTHING;

COMMIT;
