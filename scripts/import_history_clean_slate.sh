#!/usr/bin/env bash
# RNF04 clean-slate import: backup -> wipe test data -> import 48 ECs -> import 25 Releases -> attach -> verify.
# Run ONLY when the system is finished and real historical data belongs in the DB.
# Usage: bash scripts/import_history_clean_slate.sh [ec_clean.csv [releases_clean.csv [ec_release_map.csv]]]
set -euo pipefail

cd "$(dirname "$0")/.."

CSV_FILE="${1:-$HOME/Documents/ec_cleaning/ec_clean.csv}"
RELEASES_FILE="${2:-$HOME/Documents/ec_cleaning/releases_clean.csv}"
MAP_FILE="${3:-$HOME/Documents/ec_cleaning/ec_release_map.csv}"
for f in "$CSV_FILE" "$RELEASES_FILE" "$MAP_FILE"; do
    if [ ! -f "$f" ]; then
        echo "ERROR: CSV file not found: $f"
        exit 1
    fi
done
echo "Using CSVs:"
echo "  EC:       $CSV_FILE"
echo "  Releases: $RELEASES_FILE"
echo "  Map:      $MAP_FILE"

# 1. Backup (jaring pengaman) — always, no confirmation needed.
mkdir -p backups
BACKUP="backups/backup_$(date +%Y%m%d_%H%M%S).db"
sqlite3 db.sqlite3 ".backup $BACKUP"
echo "Backup saved: $BACKUP"

# 2. Show current state (read-only).
echo
echo "=== Current state ==="
uv run python manage.py shell -c "
from apps.backlog.models import EC, Release
from apps.documents.models import DocumentVersion
print(f'  EC: {EC.objects.count()} (imported: {EC.objects.filter(is_imported=True).count()})')
print(f'  Release: {Release.objects.count()}')
print(f'  DocumentVersion: {DocumentVersion.objects.count()}')
"

# 3. Confirm, then wipe test data.
echo
read -r -p "Delete ALL existing ECs and Releases (test data) now? [ketik ya] " answer
if [ "$answer" != "ya" ]; then
    echo "Aborted. Nothing changed."
    exit 0
fi

echo
echo "=== EC dry-run report (nothing written yet) ==="
uv run python manage.py import_history "$CSV_FILE"

echo
read -r -p "Report looks good. Commit the 48 ECs now? [ketik ya] " answer
if [ "$answer" != "ya" ]; then
    echo "Aborted after dry-run. Nothing written."
    exit 0
fi
uv run python manage.py import_history "$CSV_FILE" --commit

echo
echo "=== Releases dry-run report ==="
uv run python manage.py import_releases "$RELEASES_FILE" "$MAP_FILE"

echo
read -r -p "Commit the 25 Releases and link 46 ECs now? [ketik ya] " answer
if [ "$answer" != "ya" ]; then
    echo "Aborted before releases. ECs stay imported."
    exit 0
fi
uv run python manage.py import_releases "$RELEASES_FILE" "$MAP_FILE" --commit

# 4. Verify.
echo
echo "=== Verification ==="
uv run python manage.py shell -c "
from apps.backlog.models import EC, Release
from apps.backlog.services import next_ec_number
count = EC.objects.count()
nxt = next_ec_number(2026)
rel = Release.objects.count()
attached = EC.objects.filter(release__isnull=False).count()
free = EC.objects.filter(release__isnull=True).count()
print(f'  EC: {count} (harusnya 48)')
print(f'  next_ec_number(2026): {nxt} (harusnya 49)')
print(f'  Release: {rel} (harusnya 25)')
print(f'  EC tergantung Release: {attached} (harusnya 46), bebas: {free} (harusnya 2)')
if count != 48 or nxt != 49 or rel != 25 or attached != 46 or free != 2:
    print('  GAGAL: angka tidak sesuai. Restore backup bila perlu:')
    print(f'    cp \"${BACKUP}\" db.sqlite3')
    raise SystemExit(1)
print('  SEMUA BERES.')
"
