-- =====================================================================
-- Bilder je Generation statt je Modellfamilie.
--
-- Bisher wurde pro Marke/Baureihe gesucht ("Audi A4") und die passende
-- Generation erst beim Anzeigen herausgefiltert. Das geht schief, sobald
-- die Suche ueberwiegend Bilder einer anderen Generation liefert - fuer
-- einen A4 B8 blieb am Ende ein B9 uebrig.
--
-- Richtig ist, schon bei der Suche nach der Generation zu fragen
-- ("Audi A4 B8"). Die Spalte platform haelt fest, zu welcher Generation
-- ein Bild gehoert.
-- =====================================================================

BEGIN;

ALTER TABLE vehicle_images ADD COLUMN IF NOT EXISTS platform text;

DROP INDEX IF EXISTS idx_images_unique;
CREATE UNIQUE INDEX idx_images_unique
    ON vehicle_images (make, model_family, coalesce(platform, ''), file_name);
CREATE INDEX IF NOT EXISTS idx_images_platform
    ON vehicle_images (make, model_family, platform, score DESC);

-- Der bisherige Bestand stammt aus der Suche ohne Generation und ist
-- deshalb nicht zuverlaessig zuzuordnen. Er bleibt als Rueckfall
-- erhalten (platform IS NULL), wird aber nur genutzt, wenn es fuer die
-- Generation nichts Besseres gibt.
ALTER TABLE vehicle_image_lookups ADD COLUMN IF NOT EXISTS platform text;

-- Nur die Bedingung loesen; der zugehoerige Index verschwindet mit ihr.
-- (Ein direktes DROP INDEX auf einen Primaerschluessel weist Postgres ab.)
ALTER TABLE vehicle_image_lookups DROP CONSTRAINT IF EXISTS vehicle_image_lookups_pkey;
CREATE UNIQUE INDEX IF NOT EXISTS idx_image_lookups_unique
    ON vehicle_image_lookups (make, model_family, coalesce(platform, ''));

INSERT INTO schema_migrations (version) VALUES ('011_images_per_generation')
ON CONFLICT (version) DO NOTHING;

COMMIT;
