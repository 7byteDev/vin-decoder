BEGIN;

-- Bilder in der eigenen Datenbank ablegen statt bei jedem Seitenaufruf von
-- Wikimedia zu laden. Vorteile: keine fremde Abhaengigkeit im Ladepfad,
-- eigene Groessen, gleichbleibende Antwortzeiten. Die Lizenzangabe bleibt
-- an jedem Bild, weil CC-BY und CC-BY-SA die Namensnennung verlangen.
ALTER TABLE vehicle_images
    ADD COLUMN IF NOT EXISTS view text NOT NULL DEFAULT 'exterior',
    ADD COLUMN IF NOT EXISTS source_url text,
    ADD COLUMN IF NOT EXISTS image bytea,
    ADD COLUMN IF NOT EXISTS thumb bytea,
    ADD COLUMN IF NOT EXISTS content_type text,
    ADD COLUMN IF NOT EXISTS bytes integer,
    ADD COLUMN IF NOT EXISTS stored_at timestamptz;

ALTER TABLE vehicle_images DROP CONSTRAINT IF EXISTS vehicle_images_view_check;
ALTER TABLE vehicle_images ADD CONSTRAINT vehicle_images_view_check
    CHECK (view IN ('exterior', 'interior'));

-- Openverse kommt als zweite Quelle dazu: dieselbe Lizenzfamilie (CC/PD),
-- aber auch Flickr-Bestaende - dort liegen die Innenaufnahmen, die auf
-- Commons weitgehend fehlen.
ALTER TABLE vehicle_images DROP CONSTRAINT IF EXISTS vehicle_images_origin_check;
ALTER TABLE vehicle_images ADD CONSTRAINT vehicle_images_origin_check
    CHECK (origin IN ('wikidata_p18', 'commons_quality', 'commons_category',
                      'commons_search', 'openverse', 'adac', 'local'));

-- Aussenansichten zuerst, danach der Innenraum.
CREATE INDEX IF NOT EXISTS vehicle_images_view_idx
    ON vehicle_images (make, model_family, view, score DESC);

INSERT INTO schema_migrations (version) VALUES ('015_image_storage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
