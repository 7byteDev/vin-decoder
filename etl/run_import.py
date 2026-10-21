"""ETL-Kommandozeile.

    python -m etl.run_import migrate            Schema und Quellen-Seed einspielen
    python -m etl.run_import nhtsa-wmi          WMI-Stammdaten aus NHTSA vPIC laden
    python -m etl.run_import vininfo            Herstellerregeln aus vininfo laden
    python -m etl.run_import targa              Schweizer Typengenehmigungen (TARGA)
    python -m etl.run_import images             Fahrzeugbilder aus Wikimedia Commons
    python -m etl.run_import logos              Markenlogos aus Wikimedia Commons
    python -m etl.run_import all                beides nacheinander
    python -m etl.run_import status             Bestand anzeigen

Alle Importe sind wiederholbar; ein erneuter Lauf aktualisiert bestehende
Zeilen, statt Duplikate anzulegen.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .common import ROOT, connect, setup_logging

logger = logging.getLogger("etl.run")

MIGRATIONS_DIR = ROOT / "db" / "migrations"

BOOTSTRAP = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


async def cmd_migrate(args: argparse.Namespace) -> int:
    conn = await connect()
    try:
        await conn.execute(BOOTSTRAP)
        applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not files:
            logger.error("Keine Migrationen unter %s gefunden.", MIGRATIONS_DIR)
            return 1
        for path in files:
            version = path.stem
            if version in applied:
                logger.info("uebersprungen (bereits eingespielt): %s", version)
                continue
            logger.info("spiele ein: %s", version)
            await conn.execute(path.read_text(encoding="utf-8"))
        logger.info("Migrationen abgeschlossen.")
        return 0
    finally:
        await conn.close()


async def cmd_nhtsa_wmi(args: argparse.Namespace) -> int:
    from .importers import nhtsa_wmi

    conn = await connect()
    try:
        await nhtsa_wmi.run(
            conn,
            max_pages=args.max_pages,
            concurrency=args.concurrency,
            use_cache=not args.no_cache,
            focus_only=args.focus_only,
            rate=args.rate,
        )
        return 0
    finally:
        await conn.close()


async def cmd_vininfo(args: argparse.Namespace) -> int:
    from .importers import vininfo_patterns

    if args.dry_run:
        wmi_rows, pattern_rows = vininfo_patterns.collect()
        logger.info(
            "Probelauf: %s WMI-Zeilen, %s Regeln (nichts geschrieben).",
            len(wmi_rows),
            len(pattern_rows),
        )
        return 0

    conn = await connect()
    try:
        await vininfo_patterns.run(conn)
        return 0
    finally:
        await conn.close()


async def cmd_targa(args: argparse.Namespace) -> int:
    from .importers import astra_targa

    conn = await connect()
    try:
        await astra_targa.run(
            conn,
            dataset=args.dataset,
            force_download=args.force_download,
            limit=args.limit,
        )
        if not args.skip_extras:
            await astra_targa.run_extras(
                conn, kind="consumption", force_download=args.force_download
            )
            await astra_targa.run_extras(
                conn, kind="emissions", force_download=args.force_download
            )
        return 0
    finally:
        await conn.close()


async def cmd_store(args: argparse.Namespace) -> int:
    from .importers import image_backfill

    conn = await connect()
    try:
        await image_backfill.run_logos(conn)
        await image_backfill.run(conn, limit=args.limit, rate=args.rate)
        return 0
    finally:
        await conn.close()


async def cmd_gallery(args: argparse.Namespace) -> int:
    from .importers import adac_gallery

    conn = await connect()
    try:
        await adac_gallery.run(
            conn, limit=args.limit, rate=args.rate, use_cache=not args.no_cache
        )
        return 0
    finally:
        await conn.close()


async def cmd_catalog(args: argparse.Namespace) -> int:
    from .importers import adac_catalog

    conn = await connect()
    try:
        await adac_catalog.run(
            conn,
            rate=args.rate,
            use_cache=not args.no_cache,
            brand=args.brand,
            with_generations=not args.no_generations,
        )
        return 0
    finally:
        await conn.close()


async def cmd_adac(args: argparse.Namespace) -> int:
    from .importers import adac_images

    conn = await connect()
    try:
        await adac_images.run(
            conn,
            min_approvals=args.min_approvals,
            limit=args.limit,
            rate=args.rate,
            use_cache=not args.no_cache,
            make=args.make,
        )
        return 0
    finally:
        await conn.close()


async def cmd_images(args: argparse.Namespace) -> int:
    from .importers import wikimedia_images

    conn = await connect()
    try:
        await wikimedia_images.run(
            conn,
            min_approvals=args.min_approvals,
            limit=args.limit,
            rate=args.rate,
            use_cache=not args.no_cache,
            make=args.make,
            redo=args.redo,
        )
        return 0
    finally:
        await conn.close()


async def cmd_logos(args: argparse.Namespace) -> int:
    from .importers import wikimedia_logos

    conn = await connect()
    try:
        await wikimedia_logos.run(
            conn, limit=args.limit, rate=args.rate, use_cache=not args.no_cache,
            catalog_only=args.catalog_only,
        )
        return 0
    finally:
        await conn.close()


async def cmd_all(args: argparse.Namespace) -> int:
    for step in (cmd_migrate, cmd_nhtsa_wmi, cmd_vininfo, cmd_targa):
        code = await step(args)
        if code != 0:
            return code
    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    conn = await connect()
    try:
        rows = await conn.fetch(
            """
            SELECT s.key, s.license_ok, s.record_count, s.last_import_at,
                   (SELECT count(*) FROM wmi w WHERE w.source_id = s.id) AS wmi_rows,
                   (SELECT count(*) FROM manufacturer_patterns p
                     WHERE p.source_id = s.id) AS patterns,
                   (SELECT count(*) FROM type_approvals t
                     WHERE t.source_id = s.id) AS approvals
            FROM sources s ORDER BY s.license_ok DESC, s.key
            """
        )
        print(
            f"{'Quelle':<22}{'Import':<8}{'WMI':>8}{'Regeln':>9}{'Typgen.':>10}  letzter Lauf"
        )
        for r in rows:
            stamp = r["last_import_at"].strftime("%Y-%m-%d %H:%M") if r["last_import_at"] else "-"
            print(
                f"{r['key']:<22}{'ja' if r['license_ok'] else 'nein':<8}"
                f"{r['wmi_rows']:>8}{r['patterns']:>9}{r['approvals']:>10}  {stamp}"
            )
        total = await conn.fetchrow(
            "SELECT (SELECT count(DISTINCT code) FROM wmi) AS codes,"
            " (SELECT count(*) FROM manufacturer_patterns) AS patterns,"
            " (SELECT count(*) FROM type_approvals) AS approvals,"
            " (SELECT count(*) FROM type_approval_vin_patterns) AS vin_patterns,"
            " (SELECT count(*) FROM lookups_log) AS lookups"
        )
        print(
            f"\nGesamt: {total['codes']} WMI-Codes, {total['patterns']} Regeln, "
            f"{total['approvals']} Typengenehmigungen mit {total['vin_patterns']} "
            f"VIN-Mustern, {total['lookups']} Anfragen protokolliert"
        )
        return 0
    finally:
        await conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="etl.run_import", description=__doc__)
    parser.add_argument("--log-level", default="INFO")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="Schema/Seed einspielen").set_defaults(func=cmd_migrate)

    nhtsa = sub.add_parser("nhtsa-wmi", help="WMI-Stammdaten aus NHTSA vPIC")
    nhtsa.add_argument("--max-pages", type=int, default=None,
                       help="Herstellerseiten begrenzen (Test: 2)")
    nhtsa.add_argument("--concurrency", type=int, default=2)
    nhtsa.add_argument("--rate", type=float, default=1.0,
                       help="Mindestabstand zwischen Anfragen in Sekunden (Standard 1.0)")
    nhtsa.add_argument("--no-cache", action="store_true", help="Plattencache ignorieren")
    nhtsa.add_argument("--focus-only", action="store_true",
                       help="nur Europa/Tuerkei importieren")
    nhtsa.set_defaults(func=cmd_nhtsa_wmi)

    vi = sub.add_parser("vininfo", help="Herstellerregeln aus vininfo (BSD-3-Clause)")
    vi.add_argument("--dry-run", action="store_true")
    vi.set_defaults(func=cmd_vininfo)

    all_cmd = sub.add_parser("all", help="migrate + nhtsa-wmi + vininfo")
    all_cmd.add_argument("--max-pages", type=int, default=None)
    all_cmd.add_argument("--concurrency", type=int, default=2)
    all_cmd.add_argument("--rate", type=float, default=1.0)
    all_cmd.add_argument("--no-cache", action="store_true")
    all_cmd.add_argument("--focus-only", action="store_true")
    all_cmd.add_argument("--dry-run", action="store_true")
    all_cmd.add_argument("--dataset", default="automobil")
    all_cmd.add_argument("--force-download", action="store_true")
    all_cmd.add_argument("--limit", type=int, default=None)
    all_cmd.add_argument("--skip-extras", action="store_true")
    all_cmd.set_defaults(func=cmd_all)

    targa = sub.add_parser(
        "targa", help="Schweizer Typengenehmigungen (ASTRA TARGA, Open Government Data)"
    )
    targa.add_argument("--dataset", default="automobil",
                       choices=["automobil", "moto", "anhaenger"])
    targa.add_argument("--force-download", action="store_true",
                       help="Datei neu laden, auch wenn sie unveraendert ist")
    targa.add_argument("--limit", type=int, default=None, help="nur N Zeilen (Test)")
    targa.add_argument("--skip-extras", action="store_true",
                       help="Verbrauch und Emissionen nicht mitladen")
    targa.set_defaults(func=cmd_targa)

    images = sub.add_parser(
        "images", help="Fahrzeugbilder aus Wikimedia Commons (frei lizenziert)"
    )
    images.add_argument("--min-approvals", type=int, default=5,
                        help="nur Modellfamilien ab so vielen Genehmigungen")
    images.add_argument("--limit", type=int, default=400,
                        help="wie viele Familien pro Lauf")
    images.add_argument("--rate", type=float, default=1.0,
                        help="Mindestabstand zwischen Anfragen in Sekunden")
    images.add_argument("--no-cache", action="store_true")
    images.add_argument("--make", default="",
                        help="nur diese Marke (z. B. MERCEDES-BENZ)")
    images.add_argument("--redo", action="store_true",
                        help="fruehere Abfragen dieser Marke verwerfen und neu suchen")
    images.set_defaults(func=cmd_images)

    adac = sub.add_parser(
        "adac", help="Fahrzeugbilder aus dem ADAC-Autokatalog (privater Betrieb)"
    )
    adac.add_argument("--min-approvals", type=int, default=5)
    adac.add_argument("--limit", type=int, default=400)
    adac.add_argument("--rate", type=float, default=1.5,
                      help="Sekunden zwischen zwei Seitenabrufen")
    adac.add_argument("--no-cache", action="store_true")
    adac.add_argument("--make", default="", help="nur diese Marke")
    adac.set_defaults(func=cmd_adac)

    catalog = sub.add_parser(
        "catalog", help="Marken, Modelle und Baureihen des Fahrzeugkatalogs"
    )
    catalog.add_argument("--rate", type=float, default=1.2)
    catalog.add_argument("--no-cache", action="store_true")
    catalog.add_argument("--brand", default="",
                         help="nur diese Marke (Adressteil), sonst alle")
    catalog.add_argument("--no-generations", action="store_true",
                         help="nur Marken und Modelle, ohne Baureihen")
    catalog.set_defaults(func=cmd_catalog)

    gallery = sub.add_parser(
        "gallery", help="Bildergalerie je Katalog-Baureihe"
    )
    gallery.add_argument("--limit", type=int, default=400)
    gallery.add_argument("--rate", type=float, default=1.0)
    gallery.add_argument("--no-cache", action="store_true")
    gallery.set_defaults(func=cmd_gallery)

    store = sub.add_parser(
        "store", help="Fehlende Bilddateien in die Datenbank nachladen"
    )
    store.add_argument("--limit", type=int, default=500)
    store.add_argument("--rate", type=float, default=1.0)
    store.set_defaults(func=cmd_store)

    logos = sub.add_parser("logos", help="Markenlogos aus Wikimedia Commons")
    logos.add_argument("--limit", type=int, default=120, help="wie viele Marken pro Lauf")
    logos.add_argument("--rate", type=float, default=3.5,
                       help="Mindestabstand zwischen Anfragen in Sekunden")
    logos.add_argument("--no-cache", action="store_true")
    logos.add_argument("--catalog-only", action="store_true",
                       help="nur Marken, die im Fahrzeugkatalog stehen")
    logos.set_defaults(func=cmd_logos)

    sub.add_parser("status", help="Bestand anzeigen").set_defaults(func=cmd_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
