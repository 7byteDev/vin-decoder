-- =====================================================================
-- Marke und Modell im Anfrage-Log.
--
-- Fuer die Liste "aktuelle Suchen" auf der Startseite. Das sind technische
-- Fahrzeugdaten, keine personenbezogenen - dieselbe Grenze wie bisher:
-- die VIN bleibt maskiert, es wird weiterhin keine IP und kein Nutzerbezug
-- gespeichert.
-- =====================================================================

BEGIN;

ALTER TABLE lookups_log ADD COLUMN IF NOT EXISTS make text;
ALTER TABLE lookups_log ADD COLUMN IF NOT EXISTS model text;

-- Nur Anfragen mit Treffer sind fuer die Liste interessant.
CREATE INDEX IF NOT EXISTS idx_lookups_recent
    ON lookups_log (requested_at DESC)
    WHERE make IS NOT NULL;

INSERT INTO schema_migrations (version) VALUES ('007_lookup_vehicle_names')
ON CONFLICT (version) DO NOTHING;

COMMIT;
