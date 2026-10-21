#!/usr/bin/env bash
# =====================================================================
# vin-decoder: restore the bundled PostgreSQL database dump
#
# The full VIN-Decoder database (Swiss type approvals, ADAC catalog,
# images, WMI data) is too big for the git repository. It ships as a
# pg_dump custom-format file in the v1.0.0 GitHub release assets:
# https://github.com/7byteDev/vin-decoder/releases/download/v1.0.0/
#
# Usage:
#   1. docker compose up -d db        (wait until healthy)
#   2. bash scripts/restore_db.sh /path/to/vindb.dump
# =====================================================================
set -euo pipefail

DUMP=${1:?usage: $0 <path-to-vindb.dump>}

# Reassemble the split parts automatically, if only parts exist.
if [ ! -f "$DUMP" ] && ls vindb.dump.part--0 >/dev/null 2>&1; then
    echo "Assembling split parts -> vindb.dump"
    cat vindb.dump.part--* > vindb.dump
    DUMP=vindb.dump
fi

if [ -f vindb.dump.md5 ]; then
    echo "Verifying checksum ..."
    md5sum -c <(sed "s|vindb.dump|$DUMP|" vindb.dump.md5) \
        || { echo "Checksum mismatch - download corrupt?"; exit 1; }
fi

echo "Waiting for DB to become healthy ..."
docker compose up -d db
until [ -n "$(docker compose ps db --format json 2>/dev/null | grep healthy)" ]; do
    sleep 2
done

echo "Restoring dump (this can take several minutes) ..."
docker compose exec -T db pg_restore \
    --username "${POSTGRES_USER:-vindb}" \
    --dbname "${POSTGRES_DB:-vindb}" \
    --clean --if-exists --no-owner \
    < "$DUMP"

echo "Done. Start the app:  docker compose up -d api frontend"
