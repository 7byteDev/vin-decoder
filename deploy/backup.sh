#!/usr/bin/env bash
# Datenbank-Dump der VIN-Decoder-Instanz. Als taeglicher Cron-Job gedacht.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/vin-decoder}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/vin-decoder}"
KEEP_DAYS="${KEEP_DAYS:-14}"

cd "$PROJECT_DIR"
mkdir -p "$BACKUP_DIR"

# shellcheck disable=SC1091
source .env

STAMP=$(date +%Y%m%d-%H%M)
TARGET="$BACKUP_DIR/vindb-$STAMP.sql.gz"

docker compose exec -T db pg_dump -U "${POSTGRES_USER:-vindb}" -d "${POSTGRES_DB:-vindb}" \
    | gzip -9 > "$TARGET"

chmod 600 "$TARGET"
echo "Dump: $TARGET ($(du -h "$TARGET" | cut -f1))"

# Alte Dumps aufraeumen
find "$BACKUP_DIR" -name 'vindb-*.sql.gz' -mtime "+$KEEP_DAYS" -delete
echo "Vorhandene Dumps: $(find "$BACKUP_DIR" -name 'vindb-*.sql.gz' | wc -l)"
