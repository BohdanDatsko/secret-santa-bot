#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

: "${BACKUP_REMOTE:?Set BACKUP_REMOTE to an off-server rsync destination}"
command -v rsync >/dev/null 2>&1 || {
  printf '%s\n' "rsync is required for off-server backup." >&2
  exit 1
}

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
install -d -m 700 -- "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$BACKUP_DIR/secret-santa-$timestamp.dump"

trap 'status=$?; printf "Backup failed (exit=%s, file=%s)\n" "$status" "$backup_file" >&2' ERR

docker compose exec -T db sh -c \
  'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$backup_file"
chmod 600 -- "$backup_file"
find "$BACKUP_DIR" -type f -name 'secret-santa-*.dump' -mmin +20160 -delete
rsync --archive --delete --include='secret-santa-*.dump' --exclude='*' \
  --chmod=F600 -- "$BACKUP_DIR/" "$BACKUP_REMOTE/"

printf 'Backup completed and copied off-server: %s\n' "$timestamp"
