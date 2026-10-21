"""Bilder herunterladen, verkleinern und in der Datenbank ablegen.

Bisher zeigte die Detailseite direkt auf Wikimedia. Das kostet bei jedem
Aufruf eine fremde Anfrage, liefert unvorhersehbare Antwortzeiten und
haengt davon ab, dass die Datei dort liegen bleibt. Deshalb wandert jedes
ausgewaehlte Foto einmal durch diese Stelle: laden, auf eine sinnvolle
Groesse bringen, als JPEG in die Datenbank.

Zwei Groessen werden abgelegt:

* ``image`` - bis 1400 px Breite, fuer die Grossansicht
* ``thumb`` - bis 400 px Breite, fuer die Streifenleiste

Das ist erlaubt, weil ausschliesslich frei lizenzierte Bilder verarbeitet
werden (CC-BY, CC-BY-SA, gemeinfrei). Diese Lizenzen gestatten
Vervielfaeltigung und Bearbeitung ausdruecklich; verlangt wird die
Namensnennung, und die steht weiterhin an jedem Bild.
"""

from __future__ import annotations

import io
import logging

import httpx

logger = logging.getLogger("etl.images.store")

#: Groesse der Grossansicht und der Vorschau, jeweils die lange Kante.
FULL_WIDTH = 1400
THUMB_WIDTH = 400
#: JPEG-Qualitaet. 82 ist der Punkt, an dem Artefakte bei Fotos noch nicht
#: auffallen, die Datei aber deutlich kleiner ist als bei 95.
QUALITY = 82
#: Groesser laedt niemand herunter - ein Foto ueber 25 MB ist fuer eine
#: Galerie ohnehin unbrauchbar.
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


def _resize(data: bytes, width: int) -> bytes | None:
    """Ein Bild auf die gewuenschte Breite bringen und als JPEG zurueckgeben."""
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(data)) as img:
            # Aufnahmen aus Kameras tragen die Ausrichtung im Exif; ohne
            # diesen Schritt stuende manches Auto auf dem Kopf.
            img = ImageOps.exif_transpose(img)
            # Logos und viele Grafiken sind transparent. Ohne diesen
            # Schritt wuerde JPEG die Transparenz schwarz fuellen - ein
            # dunkles Logo waere dann unsichtbar. Weiss passt zum hellen
            # Kachelhintergrund.
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                white = Image.new("RGBA", img.size, (255, 255, 255, 255))
                img = Image.alpha_composite(white, img).convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")
            if img.width > width:
                height = round(img.height * width / img.width)
                img = img.resize((width, height), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=QUALITY, optimize=True,
                     progressive=True)
            return buffer.getvalue()
    except Exception as exc:  # pragma: no cover - defekte Dateien
        logger.debug("Bild nicht verarbeitbar: %s", exc)
        return None


async def fetch_and_prepare(
    client: httpx.AsyncClient,
    url: str,
    *,
    full_width: int = FULL_WIDTH,
    thumb_width: int = THUMB_WIDTH,
) -> dict[str, object] | None:
    """Ein Bild laden und beide Groessen erzeugen.

    Kommt nichts Brauchbares zurueck, wird ``None`` geliefert - der
    Aufrufer laesst den Eintrag dann ohne Datei stehen und zeigt ihn
    nicht an.
    """
    try:
        response = await client.get(url, timeout=60.0, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        logger.debug("%s: %s", url, exc)
        return None

    data = response.content
    if not data or len(data) > MAX_DOWNLOAD_BYTES:
        return None

    full = _resize(data, full_width)
    if full is None:
        return None
    thumb = _resize(data, thumb_width) or full

    return {
        "image": full,
        "thumb": thumb,
        "content_type": "image/jpeg",
        "bytes": len(full),
        "source_url": url,
    }
