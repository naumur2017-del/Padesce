#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
TARGET_DB="${2:-db.sqlite3}"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup_file> [target_db]" >&2
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

cp "$BACKUP_FILE" "$TARGET_DB"
echo "Restored $BACKUP_FILE to $TARGET_DB"
