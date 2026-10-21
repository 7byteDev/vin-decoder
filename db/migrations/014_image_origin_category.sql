BEGIN;

-- Bilder duerfen jetzt auch aus der Commons-Kategorie einer Generation
-- stammen. Die Kategorie ist von Hand gepflegt und enthaelt nur Fotos
-- genau dieser Baureihe - sauberer als die Volltextsuche, die auch
-- Nachbargenerationen und beliebige Strassenaufnahmen mitbringt.
--
-- Die vollstaendige Liste steht in Migration 015; hier bleibt sie offen,
-- damit ein spaeterer Lauf nicht an Zeilen scheitert, die inzwischen
-- weitere Ursprungsangaben tragen.
ALTER TABLE vehicle_images DROP CONSTRAINT IF EXISTS vehicle_images_origin_check;

INSERT INTO schema_migrations (version) VALUES ('014_image_origin_category')
ON CONFLICT (version) DO NOTHING;

COMMIT;
