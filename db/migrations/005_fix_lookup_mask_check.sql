-- =====================================================================
-- Fix: die Datenschutz-Leitplanke auf lookups_log war wirkungslos - und
-- schlimmer, sie hat jede korrekt maskierte VIN abgewiesen.
--
-- Alt:  CHECK (vin_masked !~ '^[A-HJ-NPR-Z0-9]{17}$')
--       Gemeint war "keine vollstaendige VIN". Uebersehen wurde, dass 'X'
--       selbst ein gueltiges VIN-Zeichen ist: die Maske "…XXXXXX" besteht
--       also aus 17 gueltigen Zeichen und wurde abgelehnt. Jeder Schreib-
--       versuch schlug fehl, das Anfrage-Log blieb leer.
--
-- Neu:  Der Nachweis wird positiv gefuehrt - die letzten sechs Stellen
--       MUESSEN die Maske sein. Das ist praezise das, was die Regel
--       eigentlich sicherstellen soll.
-- =====================================================================

BEGIN;

ALTER TABLE lookups_log DROP CONSTRAINT IF EXISTS lookups_log_masked;

ALTER TABLE lookups_log
    ADD CONSTRAINT lookups_log_masked
    CHECK (vin_masked ~ '^[A-HJ-NPR-Z0-9?]{11}XXXXXX$');

INSERT INTO schema_migrations (version) VALUES ('005_fix_lookup_mask_check')
ON CONFLICT (version) DO NOTHING;

COMMIT;
