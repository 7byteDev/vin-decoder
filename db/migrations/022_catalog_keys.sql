BEGIN;

-- Drei Fehler in den Vergleichsformen, gefunden an den groessten
-- verbliebenen Luecken:
--
--   "308", "500"   Freistehende Zahlen wurden ueberall entfernt - bei
--                  Peugeot und Fiat ist die Zahl aber der Modellname.
--                  Jetzt bleibt das erste Wort unangetastet; entfernt
--                  wird nur die Leistungsangabe dahinter.
--   "320d"         Der Katalog nennt die Baureihe "3er-Reihe". Nach dem
--                  Abschneiden der Gattung blieb "3er" stehen, was nicht
--                  zu "320d" passt. Aus "3er" wird jetzt "3".
--   "Megane"       Der Katalog schreibt "Mégane". Ohne Umschrift fiel das
--                  Akzentzeichen ersatzlos weg ("mgane").
--
-- Umschrift der Zeichen mit Akzent - unaccent ist eine Erweiterung, die
-- hier nicht vorausgesetzt werden soll.
CREATE OR REPLACE FUNCTION catalog_ascii(text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT translate(
        coalesce($1, ''),
        'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝàáâãäåèéêëìíîïòóôõöùúûüýÇçÑñŠšŽž',
        'AAAAAAEEEEIIIIOOOOOUUUUYaaaaaaeeeeiiiiooooouuuuyCcNnSsZz')
$$;

CREATE OR REPLACE FUNCTION approval_key(text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    WITH s AS (SELECT catalog_ascii($1) AS t),
    teile AS (
        SELECT split_part(t, ' ', 1) AS kopf,
               substr(t, length(split_part(t, ' ', 1)) + 1) AS rest
        FROM s
    )
    SELECT lower(regexp_replace(
        kopf || regexp_replace(
            regexp_replace(rest, '\y\d+\y', ' ', 'g'),
            '\y(qu|quattro|sb|av|avant|sw|sportback|coupe|cabrio|4m|4matic|'
            'xdrive|allrad|tdi|tfsi|tsi|hdi|dci|cdi|blue|hybrid)\y',
            ' ', 'gi'),
        '[^A-Za-z0-9]', '', 'g'))
    FROM teile
$$;

CREATE OR REPLACE FUNCTION catalog_base(text)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT lower(regexp_replace(
        regexp_replace(
            regexp_replace(catalog_ascii($1), '(-|\s)?(klasse|reihe)$', '', 'i'),
            '^([0-9]+)er$', '\1'),
        '[^A-Za-z0-9]', '', 'g'))
$$;

INSERT INTO schema_migrations (version) VALUES ('022_catalog_keys')
ON CONFLICT (version) DO NOTHING;

COMMIT;
