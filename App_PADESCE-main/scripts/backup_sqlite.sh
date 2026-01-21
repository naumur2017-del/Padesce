#!/usr/bin/env bash
set -euo pipefail

SRC_DB="${1:-db.sqlite3}"
DEST_DIR="${2:-backups}"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$DEST_DIR"
cp "$SRC_DB" "$DEST_DIR/db-$TS.sqlite3"
echo "Backup created: $DEST_DIR/db-$TS.sqlite3"
