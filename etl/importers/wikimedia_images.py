"""Importer: Fahrzeugbilder aus Wikimedia Commons.

Warum diese Quelle: Commons enthaelt zehntausende Fahrzeugfotos unter
freien Lizenzen (CC BY, CC BY-SA, gemeinfrei), mit benanntem Urheber und
maschinenlesbarer Lizenzangabe. Genau das braucht man, um Bilder zeigen zu
duerfen - anders als die lizenzierten Pressefotos kommerzieller Anbieter.

Zwei Wege, kombiniert:

* **Wikidata** kennt Fahrzeugmodelle als eigene Objekte und fuehrt dort
  ein kuratiertes Hauptbild (Eigenschaft P18). Das ist fast immer ein
  gutes, passendes Foto - aber nur eines.
* **Die Commons-Volltextsuche** liefert die restliche Galerie. Sie ist
  unschaerfer, deshalb werden die Treffer nachbewertet: Titel, die Marke
  und Modell enthalten, steigen; Motorenbilder, Innenraeume, Logos und
  Detailaufnahmen fallen.

Gespeichert werden nur Metadaten. Die Bilder selbst bleiben bei Wikimedia
und werden ueber Special:FilePath ausgeliefert - das ist die stabile,
dafuer vorgesehene Adresse.
"""

from __future__ import annotations

import logging
import re
import urllib.parse

import asyncpg

from ..common import CachedClient, chunked

logger = logging.getLogger("etl.images")

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

#: Ein beschaedigtes, ausgeschlachtetes oder verbranntes Fahrzeug ist als
#: Illustration einer Typengenehmigung unbrauchbar. Der Dateiname verraet
#: das oft nicht ("... China (12).jpg"), die Commons-Kategorien dagegen
#: schon - deshalb laeuft dieser Ausdruck ueber Name, Beschreibung UND
#: Kategorien, und er verwirft die Datei ganz statt sie nur abzuwerten.
REJECT = re.compile(
    r"accident|crash|collision|wreck|damag|destroy|burn|fire|scrap|junk|"
    r"salvage|abandon|derelict|rust|dismantl|totalled|write-?off|"
    r"unfall|schrott|ausgebrannt|verschrottet|"
    r"kaza|hurda|"
    # Renn- und Rallyefahrzeuge zeigen nicht das typengenehmigte Serienauto
    r"\bDTM\b|\brally|racing|race ?car|motorsport|safety ?car|\bWRC\b|"
    # Zubehoer- und Teilefotos zeigen kein ganzes Fahrzeug
    r"exhaust|auspuff|spare ?part|ersatzteil|tuning",
    re.I,
)

#: Titelbestandteile, die gegen ein brauchbares Fahrzeugfoto sprechen.
NEGATIVE = re.compile(
    # Innenaufnahmen sind erwuenscht (zwei Plaetze), deshalb stehen sie
    # nicht mehr hier - nur Bauteil-Nahaufnahmen bleiben ausgeschlossen.
    r"engine|motor\b|logo|badge|emblem|"
    r"wheel|rim|felge|infographic|diagram|schema|manual|advert|werbung|brochure|"
    # Detailaufnahmen einzelner Bauteile - sie zeigen nicht das Fahrzeug
    r"gear ?shift|schalthebel|steering ?wheel|lenkrad|headlight|taillight|"
    r"scheinwerfer|speedometer|tacho|"
    r"crash|unfall|accident|wreck|scrap|rust|toy|modell?auto|miniature|lego",
    re.I,
)
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def roman_numeral(index: int | None) -> str:
    """Generationsziffer, wie Commons sie in Dateinamen schreibt."""
    if not index or index >= len(ROMAN):
        return ""
    return ROMAN[index]


#: TARGA kuerzt Marken ab. Wikidata und Commons kennen aber den vollen
#: Namen: die Suche nach "VW Golf 1J" findet nichts Brauchbares, die nach
#: "Volkswagen Golf 1J" genau die richtige Generation.
MAKE_ALIASES = {
    "VW": "Volkswagen",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "ALFA ROMEO": "Alfa Romeo",
    "LAND ROVER": "Land Rover",
    "ROLLS ROYCE": "Rolls-Royce",
    "SKODA": "Skoda",
    "CITROEN": "Citroen",
    "VAUXHALL": "Vauxhall",
    "OPEL/VAUXHALL": "Opel",
}


def search_make(make: str) -> str:
    """Markenname, wie ihn Wikidata und Commons schreiben."""
    cleaned = " ".join((make or "").strip().split())
    alias = MAKE_ALIASES.get(cleaned.upper())
    if alias:
        return alias
    if cleaned.isupper():
        return "-".join(part.capitalize() for part in cleaned.split("-"))
    return cleaned


#: Baureihe aus der Fahrzeugbeschreibung der VIN.
#:
#: Manche Hersteller benennen ihre Modelle so knapp, dass der Name als
#: Suchbegriff unbrauchbar ist - bei Mercedes-Benz heisst die Baureihe
#: schlicht "S". Die eigentliche Kennung steht im VIN-Muster:
#:
#:     W1K223.33........  ->  VDS "223.33"  ->  "W223"
#:
#: Genau so benennt Wikimedia die Dateien ("MERCEDES-BENZ S-CLASS (W223)"),
#: waehrend eine Suche nach "Mercedes-Benz S" nichts Verwertbares liefert.
SERIES_BUILDERS = {
    "MERCEDES-BENZ": lambda vds: f"W{vds[:3]}" if vds[:3].isdigit() else "",
    "SMART": lambda vds: f"W{vds[:3]}" if vds[:3].isdigit() else "",
}


def series_code(make: str, vin_vds: str | None) -> str:
    """Baureihenkennung, falls die Marke eine im VIN fuehrt."""
    builder = SERIES_BUILDERS.get((make or "").strip().upper())
    if builder is None or not vin_vds:
        return ""
    cleaned = re.sub(r"[^A-Z0-9]", "", vin_vds.upper())
    return builder(cleaned) if cleaned else ""


#: Ausdrueckliche Generationsangaben in Commons-Dateinamen.
#: "VOLKSWAGEN GOLF (Mk7, Typ 5G) China.jpg" -> {"MK7", "5G"}
GENERATION_MARKERS = re.compile(r"\bMk\s?(\d{1,2})\b|\bTyp\s+([A-Z0-9]{2,6})\b", re.I)


#: Baureihe in Klammern, wie Commons sie bei den deutschen Herstellern
#: schreibt: "(W220)", "(R170)", "(F30)", "(B8)". Ohne diese Erkennung
#: rutschten Fotos einer anderen S-Klasse-Generation durch, weil im
#: Dateinamen sonst nichts auf die Baureihe hinweist.
SERIES_MARKER = re.compile(r"\(([A-Z]{1,2}\d{1,3}[A-Z]{0,2})\)")
#: Buchstabenpraefix von der Nummer trennen ("W220" -> "220"), damit
#: Plattformcode und Baureihenbezeichnung vergleichbar werden.
SERIES_PARTS = re.compile(r"^([A-Z]{1,2})(\d{1,3})([A-Z]{0,2})$")


def markers_in(name: str) -> set[str]:
    found = set()
    for mk, typ in GENERATION_MARKERS.findall(name):
        if mk:
            found.add(f"MK{mk}")
        if typ:
            found.add(typ.upper())
    for code in SERIES_MARKER.findall(name.upper()):
        found.add(code)
        parts = SERIES_PARTS.match(code)
        if parts:
            found.add(parts.group(2))
    return found


#: Jahreszahl im Dateinamen - Commons benennt Fotos fast immer so.
#: Kein abschliessendes \b: Commons schreibt Aufnahmedaten oft als
#: "20080811" am Stueck, dort steht nach dem Jahr keine Wortgrenze.
YEAR_IN_NAME = re.compile(r"(?<!\d)(19[5-9]\d|20[0-4]\d)")

#: Positive Hinweise auf eine Gesamtansicht.
POSITIVE = re.compile(r"front|rear|side|heck|seite|profil|frontansicht|20\d\d", re.I)

#: Autosalons und Praesentationen liefern die saubersten Aufnahmen -
#: freigestellter Hintergrund, ganzes Fahrzeug, gutes Licht.
SHOWROOM = re.compile(
    r"IAA|motor ?show|auto ?show|salon|mondial|geneva|genf|gims|"
    r"messe|ausstellung|presentation|press",
    re.I,
)

#: Innenaufnahmen. Zwei davon runden die Galerie ab - das Cockpit sagt
#: mehr ueber die Ausstattung als eine sechste Aussenansicht.
INTERIOR = re.compile(
    r"interior|innenraum|cockpit|dashboard|armaturenbrett|instrument panel|"
    r"innenansicht|i\.c\.|rear seat|r[uü]cksitz|kofferraum|trunk|boot space",
    re.I,
)

#: Blickrichtung einer Aussenaufnahme - fuer die Mischung in der Galerie.
ANGLES = (
    ("front", re.compile(r"front|vorn|face avant", re.I)),
    ("rear", re.compile(r"rear|heck|hinten|back|arriere", re.I)),
    ("side", re.compile(r"side|seite|profil|flank", re.I)),
)

#: Kamerakennung im Dateinamen ("1X7A0206", "IMG 0266", "DSC 7199").
#: Bilder mit derselben Kennung stammen aus einer Aufnahmeserie und zeigen
#: meist dasselbe Fahrzeug aus fast derselben Richtung. Gross geschrieben
#: und mit laufender Nummer - Kleinschreibung schliesst Woerter wie
#: "front 2013" aus.
BATCH = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{2,5})[ _-]?(\d{3,6})(?![A-Za-z0-9])")
#: Eine Jahreszahl ist keine laufende Nummer.
YEAR_ONLY = re.compile(r"^(?:19|20)\d\d$")


def view_of(file_name: str) -> str:
    """"interior" oder "exterior" - fuer die Aufteilung der Galerie."""
    return "interior" if INTERIOR.search(file_name) else "exterior"


def angle_of(file_name: str) -> str:
    for name, pattern in ANGLES:
        if pattern.search(file_name):
            return name
    return ""


def batch_of(entry: dict) -> str:
    """Kennung der Aufnahmeserie - leer, wenn es keine erkennbare gibt."""
    for prefix, number in BATCH.findall(entry.get("file_name", "")):
        if YEAR_ONLY.match(number):
            continue
        return f"{(entry.get('author') or '')[:40]}|{prefix}"
    return ""


def pick_diverse(
    entries: list[dict], limit: int, per_batch: int = 2, per_author: int = 3
) -> list[dict]:
    """Die besten Bilder auswaehlen, ohne dass eine Session dominiert.

    Im ersten Durchgang bekommt jede Blickrichtung einen Platz, damit die
    Galerie Front, Heck und Seite zeigt statt sechsmal dasselbe
    Dreiviertel. Danach wird aufgefuellt. Eine erkennbare Aufnahmeserie
    steuert hoechstens zwei Bilder bei, ein Urheber hoechstens drei -
    Bilder ohne Serienkennung begrenzt nur die Urhebergrenze.
    """
    chosen: list[dict] = []
    taken = {id(e) for e in ()}
    used_batch: dict[str, int] = {}
    used_author: dict[str, int] = {}
    used_angle: set[str] = set()

    for wanted_new_angle in (True, False):
        for entry in entries:
            if len(chosen) >= limit or id(entry) in taken:
                continue
            angle = angle_of(entry["file_name"])
            if wanted_new_angle and (not angle or angle in used_angle):
                continue
            batch = batch_of(entry)
            author = (entry.get("author") or "")[:40]
            if batch and used_batch.get(batch, 0) >= per_batch:
                continue
            if author and used_author.get(author, 0) >= per_author:
                continue
            chosen.append(entry)
            taken.add(id(entry))
            if batch:
                used_batch[batch] = used_batch.get(batch, 0) + 1
            if author:
                used_author[author] = used_author.get(author, 0) + 1
            if angle:
                used_angle.add(angle)
    return chosen


#: Nur echte Fotos, keine Zeichnungen oder Grafiken.
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")

IMAGE_INSERT = """
INSERT INTO vehicle_images (make, model_family, file_name, page_url, license,
                            license_url, author, description, width, height,
                            origin, score, image_year, platform)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
ON CONFLICT (make, model_family, coalesce(platform, ''), file_name) DO UPDATE SET
    license = EXCLUDED.license, license_url = EXCLUDED.license_url,
    author = EXCLUDED.author, score = EXCLUDED.score, origin = EXCLUDED.origin,
    image_year = EXCLUDED.image_year
"""

LOOKUP_UPSERT = """
INSERT INTO vehicle_image_lookups (make, model_family, platform, found, checked_at)
VALUES ($1, $2, $3, $4, now())
ON CONFLICT (make, model_family, coalesce(platform, '')) DO UPDATE SET
    found = EXCLUDED.found, checked_at = now()
"""

#: Generationen nach Anzahl der Genehmigungen, ungeprueft zuerst.
#: Gesucht wird je Generation, nicht je Baureihe - sonst liefert die Suche
#: Bilder der falschen Generation.
FAMILIES_QUERY = """
SELECT g.make, g.model_family AS family, g.platform, g.generation_index,
       g.year_from, g.year_to, g.approvals AS n, g.vin_vds
FROM model_generations g
WHERE g.approvals >= $1
  AND NOT EXISTS (
      SELECT 1 FROM vehicle_image_lookups l
      WHERE l.make = g.make AND l.model_family = g.model_family
        AND coalesce(l.platform, '') = g.platform
  )
  AND ($3 = '' OR g.make = $3)
ORDER BY g.approvals DESC
LIMIT $2
"""

#: Eine Marke erneut abfragen - noetig, wenn sich die Suchbegriffe geaendert
#: haben (etwa seit die Baureihe aus der VIN abgeleitet wird).
FORGET_MAKE = "DELETE FROM vehicle_image_lookups WHERE make = $1"


def _clean_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", "", str(value)).strip()
    return re.sub(r"\s+", " ", text)[:300] or None


def score_title(title: str, make: str, family: str, generation: str = "") -> int:
    """Wie gut passt der Dateiname zu Marke, Modell und Generation?

    Die Generation zaehlt am schwersten: ein Bild, dessen Name den
    Plattformcode oder die Generationsziffer traegt, ist eindeutig
    zugeordnet. Steht dort eine ANDERE Generation, faellt der Treffer raus.
    """
    name = title.lower()
    score = 0
    # Einbuchstabige Modellnamen ("S", "A") stecken in fast jedem
    # Dateinamen - sie sagen nichts aus und wuerden jeden Treffer anheben.
    if len(family) >= 2 and family.lower() in name:
        score += 4
    if generation:
        pattern = r"(^|[^a-z0-9])" + re.escape(generation.lower()) + r"([^a-z0-9]|$)"
        if re.search(pattern, name):
            score += 8
    for token in make.lower().replace("-", " ").split():
        if len(token) > 2 and token in name:
            score += 2
    if POSITIVE.search(name):
        score += 1
    if SHOWROOM.search(name):
        score += 3
    if NEGATIVE.search(name):
        score -= 6
    return score


def _file_entries(
    payload: dict | None, make: str, family: str, origin: str, generation: str = ""
) -> list[dict]:
    pages = ((payload or {}).get("query") or {}).get("pages") or {}
    out = []
    for page in pages.values():
        title = page.get("title", "")
        if not title.lower().endswith(ALLOWED_EXTENSIONS):
            continue
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        file_name = title.split(":", 1)[-1]

        # Name, Beschreibung und Kategorien zusammen pruefen: ein Unfallwagen
        # heisst im Dateinamen selten so, steht aber fast immer in einer
        # entsprechenden Kategorie.
        categories = " ".join(
            c.get("title", "") for c in (page.get("categories") or [])
        )
        haystack = " ".join(
            [
                file_name,
                _clean_html((meta.get("ImageDescription") or {}).get("value")) or "",
                categories,
            ]
        )
        if REJECT.search(haystack):
            continue
        out.append(
            {
                "file_name": file_name,
                "page_url": info.get("descriptionurl"),
                "license": _clean_html((meta.get("LicenseShortName") or {}).get("value")),
                "license_url": (meta.get("LicenseUrl") or {}).get("value"),
                "author": _clean_html((meta.get("Artist") or {}).get("value")),
                "description": _clean_html((meta.get("ImageDescription") or {}).get("value")),
                "width": info.get("width"),
                "height": info.get("height"),
                "origin": origin,
                "image_year": int(YEAR_IN_NAME.search(file_name).group(1))
                if YEAR_IN_NAME.search(file_name)
                else None,
                "score": score_title(file_name, make, family, generation)
                + {"wikidata_p18": 6, "commons_quality": 8,
                   "commons_category": 4}.get(origin, 0),
            }
        )
    return out


def _years(claims: dict, prop: str) -> list[int]:
    out = []
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("time"):
            try:
                out.append(int(value["time"][1:5]))
            except ValueError:
                continue
    return out


async def wikidata_generations(
    client: CachedClient, make: str, family: str
) -> list[dict]:
    """Generationen einer Baureihe aus Wikidata, mit Bauzeitraum und Bild.

    Wikidata fuehrt Fahrzeuggenerationen als eigene Objekte ("Volkswagen
    Golf Mk4") mit Produktionsbeginn (P580) und -ende (P582). Genau das
    fehlt unseren eigenen Daten: der Plattformcode sagt zwar, WELCHE
    Generation gemeint ist, aber nicht, wie sie in Bilddateinamen heisst.

    Der Abgleich laeuft ueber den Zeitraum - die Generation mit der
    groessten Ueberschneidung zum Bauzeitraum der Typengenehmigungen
    gewinnt. Das Ergebnis wird je Baureihe zwischengespeichert und fuer
    alle ihre Generationen wiederverwendet.
    """
    query = f"{search_make(make)} {family}"
    search = await client.get_json(
        WIKIDATA_API,
        cache_key=f"wd_gen_search_{query}",
        params={
            "action": "wbsearchentities", "search": query, "language": "en",
            "type": "item", "limit": "50", "format": "json",
        },
    )
    candidates = [
        c for c in (search or {}).get("search") or []
        if re.search(r"car|vehicle|automobile|model|van|suv|hatchback|saloon",
                     c.get("description", ""), re.I)
    ]
    if not candidates:
        return []

    entities = await client.get_json(
        WIKIDATA_API,
        cache_key=f"wd_gen_entities_{query}",
        params={
            "action": "wbgetentities", "ids": "|".join(c["id"] for c in candidates[:50]),
            "props": "claims|labels", "languages": "en", "format": "json",
        },
    )
    out = []
    for qid, entity in ((entities or {}).get("entities") or {}).items():
        claims = entity.get("claims", {})
        starts = _years(claims, "P580") or _years(claims, "P571")
        ends = _years(claims, "P582")
        images = [
            c["mainsnak"]["datavalue"]["value"]
            for c in claims.get("P18", [])
            if c.get("mainsnak", {}).get("datavalue")
        ]
        if not starts and not images:
            continue
        commons_cat = next(
            (
                c["mainsnak"]["datavalue"]["value"]
                for c in claims.get("P373", [])
                if c.get("mainsnak", {}).get("datavalue")
            ),
            "",
        )
        out.append(
            {
                "qid": qid,
                "label": entity.get("labels", {}).get("en", {}).get("value", ""),
                "year_from": min(starts) if starts else None,
                "year_to": max(ends) if ends else None,
                "images": images,
                "commons_cat": commons_cat,
            }
        )
    return out


def best_generation(
    generations: list[dict], year_from: int, year_to: int
) -> dict | None:
    """Die Generation, die unseren Bauzeitraum tatsaechlich abdeckt.

    Die groesste Ueberschneidung allein genuegt nicht: fehlt die richtige
    Generation in den Suchergebnissen, gewinnt sonst die benachbarte mit
    ein, zwei Jahren Ueberlappung - fuer einen Golf von 2004 kam so ein
    Golf Mk5 heraus. Deshalb muss die Mitte unseres Zeitraums in der
    Generation liegen; sonst lieber keine Zuordnung.
    """
    middle = (year_from + year_to) // 2
    best, best_overlap = None, 0
    for gen in generations:
        start = gen["year_from"]
        if start is None:
            continue
        end = gen["year_to"] or start + 8
        if not start - 1 <= middle <= end + 1:
            continue
        overlap = min(year_to, end) - max(year_from, start) + 1
        if overlap > best_overlap:
            best, best_overlap = gen, overlap
    return best


async def _commons_info(
    client: CachedClient, file_names: list[str], make: str, family: str, generation: str
) -> list[dict]:
    """Metadaten zu namentlich bekannten Dateien (etwa aus Wikidata P18)."""
    if not file_names:
        return []
    titles = "|".join(f"File:{name}" for name in file_names)
    payload = await client.get_json(
        COMMONS_API,
        cache_key=f"cm_info2_{abs(hash(titles)) % 10**12}",
        params={
            "action": "query", "titles": titles, "prop": "imageinfo|categories",
            "iiprop": "url|extmetadata|size",
            "cllimit": "max", "clshow": "!hidden", "format": "json",
        },
    )
    return _file_entries(payload, make, family, "wikidata_p18", generation)


async def _commons_category(
    client: CachedClient, category: str, make: str, family: str, generation: str
) -> list[dict]:
    """Fotos aus der Commons-Kategorie genau dieser Generation.

    Die Kategorie ist von Hand gepflegt und generationsrein - anders als
    die Volltextsuche, die auch die Nachbargeneration und beliebige
    Strassenaufnahmen mitbringt. Deshalb steht sie vor der Suche.
    """
    if not category:
        return []
    payload = await client.get_json(
        COMMONS_API,
        cache_key=f"cm_cat_{category}",
        params={
            "action": "query", "generator": "categorymembers",
            "gcmtitle": f"Category:{category}", "gcmtype": "file", "gcmlimit": "30",
            "prop": "imageinfo|categories", "iiprop": "url|extmetadata|size",
            "cllimit": "max", "clshow": "!hidden", "format": "json",
        },
    )
    return _file_entries(payload, make, family, "commons_category", generation)


async def _commons_quality(
    client: CachedClient, category: str, make: str, family: str, generation: str,
    *, badge: bool = True,
) -> list[dict]:
    """Ausgezeichnete oder hochaufloesende Fotos genau dieser Generation.

    Die Commons-Suche versteht zwei Operatoren, die zusammen genau das
    treffen, was wir brauchen: ``deepcategory`` durchsucht den ganzen
    Kategoriebaum der Generation, ``incategory:"Quality images"`` bleibt
    bei den Aufnahmen, die andere Commons-Autoren geprueft haben
    (Schaerfe, Belichtung, Bildaufbau). Ohne Siegel wird ersatzweise ueber
    die Aufloesung gefiltert.
    """
    if not category:
        return []
    filt = 'incategory:"Quality images"' if badge else "fileres:>2000"
    term = f'deepcategory:"{category}" {filt}'
    payload = await client.get_json(
        COMMONS_API,
        cache_key=f"cm_qual_{'q' if badge else 'r'}_{category}",
        params={
            "action": "query", "generator": "search",
            "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": "20",
            "prop": "imageinfo|categories", "iiprop": "url|extmetadata|size",
            "cllimit": "max", "clshow": "!hidden", "format": "json",
        },
    )
    origin = "commons_quality" if badge else "commons_category"
    return _file_entries(payload, make, family, origin, generation)


async def _commons_search(
    client: CachedClient, term: str, make: str, family: str, generation: str = ""
) -> list[dict]:
    """Fotos ueber die Commons-Volltextsuche.

    ``term`` ist der vollstaendige Suchbegriff - idealerweise der Name der
    Generation ("Volkswagen Golf Mk4"), sonst Marke, Baureihe und
    Plattformcode. Der Generationsbezug gehoert in die Anfrage, nicht erst
    in die Nachfilterung, sonst besteht die Trefferliste aus Bildern der
    falschen Generation.
    """
    payload = await client.get_json(
        COMMONS_API,
        cache_key=f"cm_search2_{term}",
        params={
            "action": "query", "generator": "search",
            "gsrsearch": term, "gsrnamespace": "6", "gsrlimit": "12",
            "prop": "imageinfo|categories", "iiprop": "url|extmetadata|size",
            "cllimit": "max", "clshow": "!hidden", "format": "json",
        },
    )
    return _file_entries(payload, make, family, "commons_search", generation)


async def images_for(
    client: CachedClient,
    make: str,
    family: str,
    *,
    platform: str = "",
    series: str = "",
    year_from: int | None = None,
    year_to: int | None = None,
    keep: int = 6,
) -> list[dict]:
    """Bilder einer Generation sammeln, bewerten und auswaehlen."""
    found: dict[str, dict] = {}

    # 1) Die passende Generation bei Wikidata bestimmen - ueber den
    #    Bauzeitraum, nicht ueber eine geratene Nummerierung.
    generation_label = ""
    category = ""
    if year_from and year_to and len(family) >= 2:
        generations = await wikidata_generations(client, make, family)
        match = best_generation(generations, year_from, year_to)
        if match:
            generation_label = match["label"]
            category = match.get("commons_cat", "")
            hint = generation_label.split()[-1] if generation_label else platform
            for entry in await _commons_info(
                client, match["images"][:3], make, family, hint
            ):
                found[entry["file_name"]] = entry

    # Bei knappen Modellnamen ("S") gibt es kein Wikidata-Objekt, wohl aber
    # eine Kategorie zur Baureihe aus der VIN ("Mercedes-Benz W223").
    if not category and series:
        category = f"{search_make(make)} {series}"

    # 2) Die kuratierten Quellen der Generation, beste zuerst:
    #    ausgezeichnete Fotos, dann hochaufloesende, dann die Kategorie.
    if category:
        hint = generation_label.split()[-1] if generation_label else (series or platform)
        for badge in (True, False):
            for entry in await _commons_quality(
                client, category, make, family, hint, badge=badge
            ):
                found.setdefault(entry["file_name"], entry)
        for entry in await _commons_category(client, category, make, family, hint):
            found.setdefault(entry["file_name"], entry)

    # 3) Zuletzt die Volltextsuche - beliebige Strassenaufnahmen, nur wenn
    #    die kuratierten Quellen nicht genug hergeben.
    terms: list[tuple[str, str]] = []
    if series:
        terms.append((f"{search_make(make)} {series}", series))
    if generation_label:
        terms.append((generation_label, generation_label.split()[-1]))
    if platform and len(family) >= 2:
        terms.append((f"{search_make(make)} {family} {platform}", platform))

    def enough() -> bool:
        return len([e for e in found.values() if e["score"] >= 8]) >= keep

    # Die Volltextsuche ist die unsauberste Quelle: sie liefert beliebige
    # Strassenaufnahmen. Sie laeuft nur, wenn die kuratierten Quellen
    # nicht genug hergeben.
    for term, hint in terms:
        if enough():
            break
        for entry in await _commons_search(client, term, make, family, hint):
            found.setdefault(entry["file_name"], entry)

    # Traegt der Dateiname eine ausdrueckliche Generationsangabe, muss sie
    # zu unserer passen. Ein Bild, das sich selbst als "Mk7" bezeichnet,
    # gehoert nicht zu einem Fahrzeug der vierten Generation - auch dann
    # nicht, wenn sonst nichts gefunden wurde.
    own_markers = markers_in(generation_label) | ({platform.upper()} if platform else set())
    # Der letzte Bestandteil des Generationsnamens ist bei Wikidata die
    # Baureihe ("Audi A6 C8"). Ohne ihn wuerde ein Foto "(C8)" als fremde
    # Generation aussortiert, obwohl es genau die gesuchte ist.
    if generation_label:
        tail = generation_label.split()[-1].upper()
        if SERIES_PARTS.match(tail) or re.fullmatch(r"\d{1,3}", tail):
            own_markers.add(tail)
    if platform:
        parts = SERIES_PARTS.match(platform.upper())
        if parts:
            own_markers.add(parts.group(2))
    if series:
        own_markers.add(series.upper())
        own_markers.add(series.upper().lstrip("W"))

    usable = []
    for entry in found.values():
        if entry["score"] <= 0 or (entry["width"] or 0) < 600 or not entry["license"]:
            continue
        foreign = markers_in(entry["file_name"])
        if foreign and not (foreign & own_markers):
            continue
        # Bilder ausserhalb des Bauzeitraums verwerfen, wenn ein Jahr im
        # Dateinamen steht - das haelt Nachfolgegenerationen draussen.
        year = entry.get("image_year")
        if year and year_from and year_to and not (year_from - 2 <= year <= year_to + 5):
            continue
        usable.append(entry)

    usable.sort(key=lambda e: (-e["score"], -(e["width"] or 0)))

    # Lieber vier gute Fotos als sechs, von denen zwei danebenliegen:
    # Commons-Kategorien enthalten auch fehlerhaft einsortierte Dateien
    # (im W204-Ordner liegt eine C-Klasse von 2025). Ein Mindestwert haelt
    # die draussen. Bleibt dann nichts uebrig, greift die zweite Schwelle,
    # damit selten fotografierte Baureihen nicht voellig leer ausgehen.
    strong = [e for e in usable if e["score"] >= 10]
    pool = strong or [e for e in usable if e["score"] >= 4]

    # Vier Aussen- und zwei Innenaufnahmen, je Fotosession hoechstens zwei.
    outside = [e for e in pool if view_of(e["file_name"]) == "exterior"]
    inside = [e for e in pool if view_of(e["file_name"]) == "interior"]
    selected = pick_diverse(outside, max(keep - 2, 1))
    selected += pick_diverse(inside, keep - len(selected))
    # Bleiben Plaetze frei, weil es keine Innenaufnahmen gibt, fuellen
    # weitere Aussenansichten auf.
    if len(selected) < keep:
        rest = [e for e in outside if e not in selected]
        selected += pick_diverse(rest, keep - len(selected), per_batch=3, per_author=6)
    for entry in selected:
        entry["view"] = view_of(entry["file_name"])
    return selected[:keep]


async def run(
    conn: asyncpg.Connection,
    *,
    min_approvals: int = 5,
    limit: int = 400,
    rate: float = 1.0,
    use_cache: bool = True,
    make: str = "",
    redo: bool = False,
) -> int:
    """Bilder fuer die haeufigsten Modellfamilien nachladen.

    Der Lauf ist absichtlich in Portionen geschnitten: er holt die noch
    ungeprueften Familien mit den meisten Genehmigungen und merkt sich,
    was er abgefragt hat. Ein woechentlicher Job arbeitet den Bestand so
    nach und nach ab, ohne Wikimedia zu belasten.
    """
    make = (make or "").strip().upper()
    if redo and make:
        removed = await conn.execute(FORGET_MAKE, make)
        logger.info("%s: bisherige Abfragen verworfen (%s).", make, removed)

    families = await conn.fetch(FAMILIES_QUERY, min_approvals, limit, make)
    if not families:
        logger.info("Keine offenen Generationen - nichts zu tun.")
        return 0

    logger.info("%s Generationen werden abgefragt (%.1f s Abstand).", len(families), rate)
    total = 0

    async with CachedClient(
        cache_name="wikimedia", concurrency=1, min_interval=rate, use_cache=use_cache
    ) as client:
        for index, row in enumerate(families, start=1):
            make, family, platform = row["make"], row["family"], row["platform"]
            series = series_code(make, row["vin_vds"])
            # Ohne brauchbaren Modellnamen bleibt nur die Baureihe aus der
            # VIN ("W223"). Fehlt auch die, gibt es nichts zu suchen.
            if not family or (len(family) < 2 and not series):
                continue
            try:
                entries = await images_for(
                    client, make, family,
                    platform=platform,
                    series=series,
                    year_from=row["year_from"], year_to=row["year_to"],
                )
            except Exception as exc:  # pragma: no cover - Netz/Format
                logger.warning("%s %s %s: %s", make, family, platform, exc)
                entries = []

            if entries:
                await conn.executemany(
                    IMAGE_INSERT,
                    [
                        (
                            make, family, e["file_name"], e["page_url"], e["license"],
                            e["license_url"], e["author"], e["description"],
                            e["width"], e["height"], e["origin"], e["score"],
                            e["image_year"], platform,
                        )
                        for e in entries
                    ],
                )
            await conn.execute(LOOKUP_UPSERT, make, family, platform, len(entries))
            total += len(entries)

            if index % 25 == 0:
                logger.info("  %s/%s Familien, %s Bilder", index, len(families), total)

    logger.info("Bildimport fertig: %s Bilder fuer %s Familien.", total, len(families))
    return total


def file_url(file_name: str, width: int = 800) -> str:
    """Stabile Ausliefer-Adresse eines Commons-Bildes."""
    return (
        "https://commons.wikimedia.org/wiki/Special:FilePath/"
        f"{urllib.parse.quote(file_name)}?width={width}"
    )


__all__ = ["chunked", "file_url", "images_for", "run", "score_title"]
