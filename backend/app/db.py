"""Datenbankzugriff (asyncpg).

Bewusst ohne ORM: das Schema ist klein, die Abfragen sind lesbar, und die
ETL-Pipeline nutzt denselben Treiber. Faellt die Datenbank aus oder ist keine
konfiguriert, laeuft die API im Nur-Struktur-Modus weiter - der Decoder
liefert dann immer noch das deterministische Ergebnis.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class Database:
    """Duenner Wrapper um einen asyncpg-Pool."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @property
    def available(self) -> bool:
        return self._pool is not None

    async def connect(self, *, min_size: int = 1, max_size: int = 10) -> bool:
        if not self._dsn:
            logger.info("Keine DATABASE_URL gesetzt - Nur-Struktur-Modus aktiv.")
            return False
        try:
            self._pool = await asyncpg.create_pool(
                self._dsn, min_size=min_size, max_size=max_size, command_timeout=10
            )
            logger.info("Datenbankverbindung hergestellt.")
            return True
        except Exception as exc:  # pragma: no cover - abhaengig von der Umgebung
            logger.error("Datenbankverbindung fehlgeschlagen: %s", exc)
            self._pool = None
            return False

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        if self._pool is None:
            return None
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query: str, *args: Any) -> str | None:
        if self._pool is None:
            return None
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def healthy(self) -> bool:
        try:
            row = await self.fetchrow("SELECT 1 AS ok")
            return bool(row and row["ok"] == 1)
        except Exception:  # pragma: no cover
            return False


# ---------------------------------------------------------------------------
# Abfragen (Repository)
# ---------------------------------------------------------------------------

WMI_QUERY = """
SELECT w.code, w.manufacturer_name, w.common_name, w.country, w.country_code,
       w.vehicle_type, w.confidence, s.key AS source_key, s.reliability
FROM wmi w
JOIN sources s ON s.id = w.source_id
WHERE w.code = ANY($1::text[]) AND s.license_ok
ORDER BY char_length(w.code) DESC, s.reliability DESC
"""

PATTERN_QUERY = """
SELECT p.wmi_code, p.attribute, p.positions, p.match_type, p.pattern,
       p.value, p.value_i18n, p.year_from, p.year_to, p.confidence,
       s.key AS source_key, s.reliability
FROM manufacturer_patterns p
JOIN sources s ON s.id = p.source_id
WHERE (p.wmi_code = ANY($1::text[]) OR p.wmi_code = '*') AND s.license_ok
"""

VEHICLE_REFERENCE_QUERY = """
SELECT v.*, s.key AS source_key, s.reliability
FROM vehicles_reference v
JOIN sources s ON s.id = v.source_id
WHERE v.wmi_code = ANY($1::text[])
  AND ($2::smallint IS NULL OR v.model_year IS NULL OR v.model_year = $2)
  AND $3 LIKE v.vin_prefix || '%'
ORDER BY char_length(v.vin_prefix) DESC, s.reliability DESC
LIMIT 25
"""

LOG_INSERT = """
INSERT INTO lookups_log (vin_masked, wmi_code, model_year, status,
                         overall_confidence, sources_used, conflicts,
                         duration_ms, lang, make, model)
VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb, $8, $9, $10, $11)
"""

#: Zuletzt gesuchte Fahrzeuge fuer die Startseite. Je maskierter VIN nur
#: der neueste Eintrag, damit wiederholte Abfragen die Liste nicht fluten.
RECENT_LOOKUPS_QUERY = """
SELECT DISTINCT ON (vin_masked)
       vin_masked, make, model, model_year, requested_at
FROM lookups_log
WHERE make IS NOT NULL AND requested_at > now() - interval '30 days'
ORDER BY vin_masked, requested_at DESC
LIMIT $1
"""

SOURCES_QUERY = """
SELECT key, name, url, license, license_ok, attribution, reliability,
       region_focus, last_import_at, record_count, notes
FROM sources
ORDER BY license_ok DESC, reliability DESC, key
"""

STATS_QUERY = """
SELECT
  (SELECT count(*) FROM wmi) AS wmi_rows,
  (SELECT count(DISTINCT code) FROM wmi) AS wmi_codes,
  (SELECT count(*) FROM manufacturer_patterns) AS patterns,
  (SELECT count(*) FROM vehicles_reference) AS reference_vehicles,
  (SELECT count(*) FROM sources WHERE license_ok) AS active_sources,
  (SELECT count(*) FROM lookups_log) AS lookups
"""


# ---------------------------------------------------------------------------
# Typengenehmigungen (TARGA)
# ---------------------------------------------------------------------------

#: Suche ueber alle Praefixlaengen der VIN.
#:
#: Zwei Feinheiten, die den Unterschied machen:
#:
#: * Der Regex-Test laeuft in SQL, nicht erst danach in Python. Sonst
#:   schneidet das LIMIT die passenden Zeilen ab, bevor sie geprueft
#:   werden - bei Marken mit tausenden Zeilen je Praefix (VW-Konzern)
#:   kommt sonst gar kein Treffer zurueck.
#: * Die Spezifitaet misst sich an den FESTEN Zeichen des Musters, nicht
#:   an der Praefixlaenge. "TMB...1U........." hat zwar nur das Praefix
#:   "TMB", legt aber auch die Positionen 7-8 fest (Typschluessel des
#:   VW-Konzerns) und ist damit deutlich spezifischer als sein Praefix.
TYPE_APPROVAL_QUERY = """
WITH treffer AS (
    SELECT p.type_approval_id, p.prefix, p.regex, p.pattern,
           char_length(replace(p.pattern, '.', '')) AS fixed_chars
    FROM type_approval_vin_patterns p
    WHERE p.prefix = ANY($1::text[])
      AND (p.regex IS NULL OR $3 ~ p.regex)
),
beste AS (
    SELECT max(fixed_chars) AS n FROM treffer
)
SELECT ta.id, ta.approval_number, ta.approval_date, ta.eu_approval_number,
       ta.make, ta.model, ta.variant, ta.manufacturer, ta.vehicle_kind,
       ta.vehicle_class, ta.body_form, ta.engine_make, ta.engine_model,
       ta.engine_code, ta.fuel_type, ta.displacement_ccm, ta.power_kw,
       ta.torque_nm, ta.drive_type, ta.transmission, ta.gears, ta.doors,
       ta.seats_total, ta.top_speed_kmh, ta.length_mm, ta.width_mm,
       ta.height_mm, ta.wheelbase_mm, ta.weight_kg, ta.max_weight_kg,
       ta.model_year_from, ta.confidence,
       t.prefix, t.regex, t.pattern, t.fixed_chars,
       s.key AS source_key, s.reliability
FROM treffer t
JOIN beste b ON t.fixed_chars = b.n
JOIN type_approvals ta ON ta.id = t.type_approval_id
JOIN sources s ON s.id = ta.source_id
WHERE s.license_ok
ORDER BY ta.approval_date DESC NULLS LAST, ta.id
LIMIT $2
"""

TYPE_APPROVAL_DETAIL_QUERY = """
SELECT ta.*, s.key AS source_key, s.name AS source_name, s.attribution,
       (SELECT array_agg(DISTINCT p.pattern)
          FROM type_approval_vin_patterns p
         WHERE p.type_approval_id = ta.id) AS vin_patterns
FROM type_approvals ta
JOIN sources s ON s.id = ta.source_id
WHERE ta.id = $1
"""


#: Verbrauch und Emissionen zu einer Genehmigung. Beide Datensaetze fuehren
#: je Getriebevariante eine eigene Zeile, deshalb kommen mehrere zurueck.
TYPE_APPROVAL_EXTRAS_QUERY = """
SELECT kind, fuel_type, transmission, axle_ratio,
       consumption_l100, co2_g_km, consumption_wltp_l100, co2_wltp_g_km,
       electric_kwh100, electric_range_km, efficiency_category,
       emission_code, exhaust_code, cylinders, displacement_ccm, power_kw,
       data
FROM type_approval_extras
WHERE approval_number = $1
ORDER BY kind, transmission NULLS LAST, id
LIMIT 40
"""


#: Bilder zur Modellfamilie. Die Zuordnung laeuft ueber Marke und das erste
#: Wort des Modellnamens - ein Foto zeigt die Baureihe, nicht die einzelne
#: Motorisierung.
#: Bilder zur Baureihe, eingegrenzt auf die richtige Generation.
#:
#: Die Generation kommt aus model_generations (abgeleitet aus dem
#: Plattformcode der Typengenehmigung). Ein Bild passt, wenn seine
#: Jahreszahl in den Bauzeitraum faellt - mit etwas Luft nach hinten,
#: weil Fotos auch Jahre nach Produktionsende entstehen.
#:
#: Zusaetzlich zaehlt der Dateiname: enthaelt er den Plattformcode
#: ("Audi A4 B8 ...") oder die roemische Generationsziffer
#: ("Octavia II ..."), ist der Treffer sicher richtig.
VEHICLE_IMAGES_QUERY = """
WITH passend AS (
    SELECT * FROM vehicle_images
    WHERE make = $1 AND model_family = $2 AND platform = $4 AND $4 <> ''
),
auswahl AS (
    -- Gibt es Bilder, die gezielt zu dieser Generation gesucht wurden,
    -- zaehlen nur die. Ein Bild der falschen Generation ist schlechter
    -- als gar keines.
    SELECT * FROM passend
    UNION ALL
    SELECT * FROM vehicle_images
    WHERE make = $1 AND model_family = $2
      AND NOT EXISTS (SELECT 1 FROM passend)
)
SELECT id, file_name, page_url, license, license_url, author, description,
       width, height, origin, score, image_year, view,
       (image IS NOT NULL) AS stored
FROM auswahl i
ORDER BY
    -- eigene, bereits abgelegte Bilder zuerst: sie sind professionell
    -- aufgenommen und liegen in der gewuenschten Groesse vor
    CASE WHEN i.image IS NOT NULL THEN 0 ELSE 1 END,
    -- Aussenansichten vor dem Innenraum
    CASE WHEN i.view = 'interior' THEN 1 ELSE 0 END,
    -- Generationsangabe im Dateinamen zaehlt am meisten
    CASE
        WHEN $4 <> '' AND i.file_name ~* ('(^|[^A-Za-z0-9])' || $4 || '([^A-Za-z0-9]|$)')
            THEN 0
        ELSE 1
    END,
    -- danach: Naehe zum Modelljahr
    CASE WHEN $3::smallint IS NULL OR i.image_year IS NULL THEN 1 ELSE 0 END,
    abs(coalesce(i.image_year, 0) - coalesce($3::smallint, 0)),
    i.score DESC,
    i.width DESC
LIMIT 8
"""

#: Generation zu einer Genehmigung (fuer die Bildauswahl).
MODEL_GENERATION_QUERY = """
SELECT platform, year_from, year_to, generation_index
FROM model_generations
WHERE make = $1 AND model_family = $2 AND platform = $3
"""


#: Markenlogo (Wikimedia Commons, ueber Wikidata P154 ausgewaehlt).
BRAND_LOGO_QUERY = """
SELECT file_name, page_url, license, license_url, author, width, height,
       (image IS NOT NULL) AS stored
FROM brand_logos
WHERE make = $1
"""

#: Ein abgelegtes Markenlogo ausliefern.
STORED_LOGO_QUERY = """
SELECT image, content_type FROM brand_logos WHERE make = $1 AND image IS NOT NULL
"""


#: Ein in der Datenbank abgelegtes Bild ausliefern.
STORED_IMAGE_QUERY = """
SELECT image, thumb, content_type FROM vehicle_images WHERE id = $1
"""

# ---------------------------------------------------------------------------
# Blaettern nach Marke: Marke -> Modell -> Generation -> Fahrzeug
# ---------------------------------------------------------------------------

#: Marken mit Fahrzeugzahl und Logo. Sortiert nach Bestand, wie es der
#: Nutzer erwartet - die haeufigen Marken zuerst.
BRANDS_QUERY = """
-- Die Uebersicht kommt aus dem Katalog, nicht aus unseren Genehmigungen:
-- der Modellname im Typenschein ist Freitext und laesst sich nicht
-- verlaesslich in Baureihen schneiden. Die Fahrzeugzahl daneben ist
-- unsere - sie zeigt, wozu wir technische Daten haben.
SELECT b.slug, b.name, b.models, b.logo_thumb,
       coalesce((SELECT count(*) FROM approval_catalog a
                  WHERE a.brand_slug = b.slug), 0) AS vehicles
FROM catalog_brands b
ORDER BY vehicles DESC, b.name
"""

#: Modelle einer Marke mit der Zahl ihrer Generationen.
BRAND_MODELS_QUERY = """
SELECT m.slug, m.name, m.generations, m.thumb,
       coalesce((SELECT count(*) FROM approval_catalog a
                  WHERE a.brand_slug = m.brand_slug AND a.model_slug = m.slug),
                0) AS vehicles,
       (SELECT min(g.year_from) FROM catalog_generations g
         WHERE g.brand_slug = m.brand_slug AND g.model_slug = m.slug) AS year_from,
       (SELECT max(coalesce(g.year_to, g.year_from)) FROM catalog_generations g
         WHERE g.brand_slug = m.brand_slug AND g.model_slug = m.slug) AS year_to
FROM catalog_models m
WHERE m.brand_slug = $1
-- Reihenfolge wie im Katalog: erst die Namen mit Buchstaben (A1, Q5,
-- e-tron), danach die reinen Zahlenreihen (1er, 3er, 100, 3200 CS) nach
-- ihrer Zahl. Alphabetisch allein wuerde "100" vor "A1" stellen.
ORDER BY (m.name ~ '^[0-9]')::int,
         CASE WHEN m.name ~ '^[0-9]'
              THEN (substring(m.name from '^[0-9]+'))::int END,
         lower(m.name)
"""

#: Generationen eines Modells, neueste zuerst - dazu ein Bild.
MODEL_GENERATIONS_QUERY = """
SELECT g.slug, g.name, g.year_from, g.year_to, g.thumb,
       coalesce((SELECT count(*) FROM approval_catalog a
                  WHERE a.brand_slug = g.brand_slug AND a.model_slug = g.model_slug
                    AND a.generation_slug = g.slug), 0) AS vehicles
FROM catalog_generations g
WHERE g.brand_slug = $1 AND g.model_slug = $2
ORDER BY g.year_from DESC NULLS LAST, g.slug
"""

#: Fahrzeuge einer Generation. Technisch gleiche Genehmigungen werden zu
#: einer Zeile zusammengefasst - mehr als die Haelfte des Bestands ist
#: doppelt gefuehrt, und der Unterschied liegt nur in der Nummer.
GENERATION_VEHICLES_QUERY = """
-- Technisch gleiche Genehmigungen stehen in einer Zeile: mehr als die
-- Haelfte des Bestands ist doppelt gefuehrt, unterschieden nur durch die
-- Genehmigungsnummer.
SELECT min(t.id) AS id,
       t.model, t.fuel_type, t.power_kw, t.transmission, t.gears,
       t.displacement_ccm, t.drive_type, t.body_form, t.doors,
       min(t.model_year_from) AS year_from, max(t.model_year_from) AS year_to,
       count(*) AS approvals,
       array_agg(DISTINCT t.approval_number) FILTER (
           WHERE t.approval_number IS NOT NULL) AS approval_numbers
FROM approval_catalog a
JOIN type_approvals t ON t.id = a.approval_id
WHERE a.brand_slug = $1 AND a.model_slug = $2 AND a.generation_slug = $3
GROUP BY t.model, t.fuel_type, t.power_kw, t.transmission, t.gears,
         t.displacement_ccm, t.drive_type, t.body_form, t.doors
ORDER BY t.power_kw NULLS LAST, t.model
"""

#: Ein Katalogbild ausliefern (Modell oder Baureihe).
CATALOG_MODEL_IMAGE = """
SELECT image, thumb FROM catalog_models WHERE brand_slug = $1 AND slug = $2
"""
CATALOG_GENERATION_IMAGE = """
SELECT image, thumb FROM catalog_generations
WHERE brand_slug = $1 AND model_slug = $2 AND slug = $3
"""


#: Bild der Katalog-Baureihe zu einer Typengenehmigung. Es stammt aus dem
#: Fahrzeugkatalog und zeigt genau diese Generation - anders als die
#: Strassenaufnahmen, die nur ueber Marke und Modellname gefunden wurden.
CATALOG_IMAGE_FOR_APPROVAL = """
SELECT a.brand_slug, a.model_slug, a.generation_slug,
       (g.image IS NOT NULL) AS has_image
FROM approval_catalog a
JOIN catalog_generations g
  ON g.brand_slug = a.brand_slug AND g.model_slug = a.model_slug
 AND g.slug = a.generation_slug
WHERE a.approval_id = $1
"""


#: Galerie der Katalog-Baureihe zu einer Typengenehmigung.
CATALOG_GALLERY_FOR_APPROVAL = """
SELECT i.brand_slug, i.model_slug, i.generation_slug, i.position, i.source_url
FROM approval_catalog a
JOIN catalog_generation_images i
  ON i.brand_slug = a.brand_slug AND i.model_slug = a.model_slug
 AND i.generation_slug = a.generation_slug
WHERE a.approval_id = $1 AND i.image IS NOT NULL
ORDER BY i.position
"""

#: Ein Bild der Galerie ausliefern.
CATALOG_GALLERY_IMAGE = """
SELECT image, thumb FROM catalog_generation_images
WHERE brand_slug = $1 AND model_slug = $2 AND generation_slug = $3
  AND position = $4
"""
