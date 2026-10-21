BEGIN;

-- Auch die Markenlogos in der eigenen Datenbank ablegen.
--
-- Bisher zeigte die Markenuebersicht direkt auf Wikimedia: 90 Logos =
-- 90 fremde Anfragen beim Seitenaufbau, sichtbar als nachladende Kacheln.
-- Mit eigener Ablage kommt alles vom eigenen Server.
ALTER TABLE brand_logos
    ADD COLUMN IF NOT EXISTS image bytea,
    ADD COLUMN IF NOT EXISTS content_type text,
    ADD COLUMN IF NOT EXISTS bytes integer,
    ADD COLUMN IF NOT EXISTS stored_at timestamptz;

INSERT INTO schema_migrations (version) VALUES ('017_local_logos')
ON CONFLICT (version) DO NOTHING;

COMMIT;
