BEGIN;

-- Kleine Fassung des Logos fuer die Markenuebersicht.
--
-- Dort stehen 90 Logos nebeneinander. Als einzelne Anfragen ausgeliefert
-- reihen sie sich in die sechs Verbindungen des Browsers ein und brauchen
-- ueber eine Sekunde. Diese Fassung ist klein genug, um direkt in die
-- Seite eingebettet zu werden - dann kommt sie ohne eigene Anfrage.
ALTER TABLE brand_logos ADD COLUMN IF NOT EXISTS thumb bytea;

INSERT INTO schema_migrations (version) VALUES ('018_logo_thumb')
ON CONFLICT (version) DO NOTHING;

COMMIT;
