-- =====================================================================
-- Aufnahmejahr des Bildes.
--
-- Commons-Dateinamen tragen fast immer eine Jahreszahl ("Skoda Octavia II
-- 2009 front.jpg"). Ohne sie landet bei einem Fahrzeug von 2011 schon mal
-- ein Foto von 1959 an erster Stelle. Mit ihr laesst sich die Galerie nach
-- Naehe zum Modelljahr sortieren.
-- =====================================================================

BEGIN;

ALTER TABLE vehicle_images ADD COLUMN IF NOT EXISTS image_year smallint;

UPDATE vehicle_images
SET image_year = NULLIF(substring(file_name from '\y(19[5-9]\d|20[0-4]\d)\y'), '')::smallint
WHERE image_year IS NULL;

CREATE INDEX IF NOT EXISTS idx_images_year ON vehicle_images (make, model_family, image_year);

INSERT INTO schema_migrations (version) VALUES ('009_image_year')
ON CONFLICT (version) DO NOTHING;

COMMIT;
