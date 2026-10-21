-- =====================================================================
-- Fix: mehrdeutige Herstellerregeln duerfen nicht verloren gehen.
--
-- Der urspruengliche Unique-Index liess pro (WMI, Attribut, Position,
-- Muster) nur EINEN Wert zu. Genau bei den mehrdeutigen Regeln ist das
-- falsch: bei Nissan steht z. B. an Position 7 die '1' je nach Baureihe
-- fuer "Sedan, 4-Door" oder "Standard Body Truck". Beim Import hat der
-- zweite Wert den ersten ueberschrieben - 872 von 4116 Regeln gingen so
-- verloren.
--
-- Richtig ist, beide Auspraegungen als eigene Zeilen zu behalten. Die
-- Engine fuehrt sie ohnehin zusammen: der bestbewertete Wert gewinnt,
-- die uebrigen erscheinen als Alternative, und der Widerspruch wird
-- ausgewiesen statt stillschweigend aufgeloest.
-- =====================================================================

BEGIN;

DROP INDEX IF EXISTS idx_patterns_unique;

CREATE UNIQUE INDEX idx_patterns_unique
    ON manufacturer_patterns
       (wmi_code, attribute, positions, pattern, value, source_id, COALESCE(year_from, 0));

INSERT INTO schema_migrations (version) VALUES ('003_patterns_keep_alternatives')
ON CONFLICT (version) DO NOTHING;

COMMIT;
