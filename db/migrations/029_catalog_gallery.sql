BEGIN;

-- Bildergalerie je Katalog-Baureihe.
--
-- Die Kachel des Katalogs liefert ein Bild. Auf der Fahrzeugseite darunter
-- stehen fuenf bis sechs Aufnahmen aus verschiedenen Richtungen - genau
-- die, die auf unserer Detailseite gebraucht werden. Sie haengen an der
-- Baureihe, nicht an der einzelnen Genehmigung: eine Genehmigung deckt
-- mehrere Motorisierungen ab, die alle gleich aussehen.
CREATE TABLE IF NOT EXISTS catalog_generation_images (
    brand_slug      text NOT NULL,
    model_slug      text NOT NULL,
    generation_slug text NOT NULL,
    position        integer NOT NULL,
    file_name       text NOT NULL,
    source_url      text,
    image           bytea,
    thumb           bytea,
    imported_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_slug, model_slug, generation_slug, position)
);

INSERT INTO schema_migrations (version) VALUES ('029_catalog_gallery')
ON CONFLICT (version) DO NOTHING;

COMMIT;
