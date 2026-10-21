-- =====================================================================
-- Fahrzeugbilder aus Wikimedia Commons.
--
-- Quelle sind frei lizenzierte Fotos (CC BY, CC BY-SA, gemeinfrei) von
-- Wikimedia Commons, ausgewaehlt ueber Wikidata (Eigenschaft P18 des
-- Fahrzeugmodells) und die Commons-Volltextsuche.
--
-- Gespeichert werden nur Metadaten und der Dateiname - die Bilder selbst
-- liegen weiterhin bei Wikimedia und werden von dort ausgeliefert. Lizenz
-- und Urheber stehen bei jedem Bild dabei, weil beide Lizenzfamilien die
-- Namensnennung verlangen.
--
-- Zuordnung ueber Marke + Modellfamilie, nicht ueber die einzelne
-- Genehmigung: die Typengenehmigung kennt kein Bild, und ein Foto zeigt
-- ohnehin die Baureihe, nicht die konkrete Motorisierung.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS vehicle_images (
    id            bigserial PRIMARY KEY,
    make          text NOT NULL,
    model_family  text NOT NULL,
    file_name     text NOT NULL,
    page_url      text,
    license       text,
    license_url   text,
    author        text,
    description   text,
    width         integer,
    height        integer,
    origin        text NOT NULL DEFAULT 'commons_search'
                  CHECK (origin IN ('wikidata_p18', 'commons_search')),
    score         integer NOT NULL DEFAULT 0,
    imported_at   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_images_unique
    ON vehicle_images (make, model_family, file_name);
CREATE INDEX IF NOT EXISTS idx_images_lookup
    ON vehicle_images (make, model_family, score DESC);

-- Merkt sich, welche Familien schon abgefragt wurden - auch die ohne
-- Treffer, damit ein Wiederholungslauf sie nicht erneut anfragt.
CREATE TABLE IF NOT EXISTS vehicle_image_lookups (
    make          text NOT NULL,
    model_family  text NOT NULL,
    found         integer NOT NULL DEFAULT 0,
    checked_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (make, model_family)
);

INSERT INTO schema_migrations (version) VALUES ('008_vehicle_images')
ON CONFLICT (version) DO NOTHING;

COMMIT;
