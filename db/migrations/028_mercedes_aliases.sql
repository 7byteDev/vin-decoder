BEGIN;

-- Zwei Mercedes-Schreibweisen, die der Katalog anders fuehrt:
--   "AMG C 63"  -> C-Klasse (der Katalog kennt keine eigene AMG-Baureihe)
--   "ML 350"    -> M-Klasse
-- Der grosse Rest der offenen Mercedes-Eintraege sind Lastwagen
-- (Actros, Arocs, Antos, Atego, Axor, Econic) und Busse der O-Reihe.
-- Sie stehen nicht im Katalog und bekommen deshalb auch keine Regel.
INSERT INTO catalog_model_alias (brand_slug, prefix, model_slug) VALUES
    ('mercedes-benz', 'amga', 'a-klasse'),
    ('mercedes-benz', 'amgb', 'b-klasse'),
    ('mercedes-benz', 'amgc', 'c-klasse'),
    ('mercedes-benz', 'amge', 'e-klasse'),
    ('mercedes-benz', 'amgg', 'g-klasse'),
    ('mercedes-benz', 'amgs', 's-klasse'),
    ('mercedes-benz', 'amgsl', 'sl-klasse'),
    ('mercedes-benz', 'amgslk', 'slk-klasse'),
    ('mercedes-benz', 'ml', 'm-klasse'),
    ('mercedes-benz', 'gl', 'gl-klasse')
ON CONFLICT DO NOTHING;

INSERT INTO schema_migrations (version) VALUES ('028_mercedes_aliases')
ON CONFLICT (version) DO NOTHING;

COMMIT;
