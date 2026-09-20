#!/usr/bin/env bash
# Database backup script for the NIFTY 200 Opportunity Scanner's Postgres
# database. Run on a schedule (see the cron example below) - NOT part of
# the application's own runtime, since backup and restore should keep
# working even if the app itself is down.
#
# Reads connection details from the SAME environment variable the app uses
# (DATABASE_URL) - never hardcode a password in this script.
#
# Usage:
#   ./backup.sh                    # runs a backup now
#   RETENTION_DAYS=30 ./backup.sh  # override the default retention

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/nifty200-scanner}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/nifty200_scanner_${TIMESTAMP}.sql.gz"

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is not set. Refusing to guess connection details." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

echo "Backing up to ${BACKUP_FILE} ..."
pg_dump --no-owner --no-privileges --format=plain "$DATABASE_URL" | gzip > "$BACKUP_FILE"
echo "Backup complete: $(du -h "$BACKUP_FILE" | cut -f1)"

# Retention: delete local backups older than RETENTION_DAYS. If you're
# shipping backups to S3/GCS/etc. (recommended - see DEPLOYMENT.md), apply
# a lifecycle policy there too; this only prunes the local copy.
echo "Pruning local backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_DIR" -name "nifty200_scanner_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "Done."

# --------------------------------------------------------------------------
# CRON EXAMPLE (daily at 02:00 IST / 20:30 UTC, after market close):
#   30 20 * * * DATABASE_URL="postgresql://..." /path/to/backup.sh >> /var/log/nifty200-backup.log 2>&1
#
# RESTORE:
#   gunzip -c nifty200_scanner_TIMESTAMP.sql.gz | psql "$DATABASE_URL"
#   (Restoring into a FRESH/empty database is strongly recommended over
#   restoring on top of a live one - create a new database, restore into
#   it, verify, then cut over.)
#
# RECOMMENDED PRODUCTION SETUP (beyond this script):
#   - Ship backups off the app host immediately after creation (aws s3 cp,
#     gsutil cp, or your provider's equivalent) - a backup that lives only
#     on the same disk as the database it backs up doesn't protect against
#     host/disk failure.
#   - If using a managed Postgres (RDS, Cloud SQL, etc.), prefer the
#     provider's native automated snapshots/point-in-time-recovery over
#     this script, and use this script only for an additional
#     portable/offsite copy.
#   - Periodically test a real restore, not just that the backup file
#     exists - an untested backup is not a verified backup.
# --------------------------------------------------------------------------
