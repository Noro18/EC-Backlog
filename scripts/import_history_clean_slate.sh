#!/usr/bin/env bash
# RNF04 clean-slate import: backup -> wipe test ECs -> dry-run -> commit -> verify.
# Run ONLY when the system is finished and real historical data belongs in the DB.
# Usage: bash scripts/import_history_clean_slate.sh [path/to/ec_clean.csv]
set -euo pipefail

cd "$(dirname "$0")/.."

CSV_FILE="${1:-$HOME/Documents/ec_cleaning/ec_clean.csv}"
if [ ! -f "$CSV_FILE" ]; then
    echo "ERROR: CSV file not found: $CSV_FILE"
    exit 1
fi
echo "Using CSV: $CSV_FILE"

# 1. Backup (jaring pengaman) — always, no confirmation needed.
mkdir -p backups
BACKUP="backups/backup_$(date +%Y%m%d_%H%M%S).db"
sqlite3 db.sqlite3 ".backup $BACKUP"
echo "Backup saved: $BACKUP"

# 2. Show current state (read-only).
echo
echo "=== Current state ==="
uv run python manage.py shell -c "
from apps.backlog.models import EC
from apps.documents.models import DocumentVersion
print(f'  EC: {EC.objects.count()} (imported: {EC.objects.filter(is_imported=True).count()})')
print(f'  DocumentVersion: {DocumentVersion.objects.count()}')
"

# 3. Confirm, then wipe test data.
echo
read -r -p "Delete ALL existing ECs (test data) now? [ketik ya] " answer
if [ "$answer" != "ya" ]; then
    echo "Aborted. Nothing changed."
    exit 0
fi

echo
echo "=== Dry-run report (nothing written yet) ==="
uv run python manage.py import_history "$CSV_FILE"

# 4. Confirm, then write.
echo
read -r -p "Report looks good. Write --commit now? [ketik ya] " answer
if [ "$answer" != "ya" ]; then
    echo "Aborted after dry-run. Nothing written."
    exit 0
fi

echo
echo "=== Committing ==="
uv run python manage.py import_history "$CSV_FILE" --commit

# 5. Verify.
echo
echo "=== Verification ==="
uv run python manage.py shell -c "
from apps.backlog.models import EC
from apps.backlog.services import next_ec_number
count = EC.objects.count()
nxt = next_ec_number(2026)
print(f'  EC: {count} (harusnya 48)')
print(f'  next_ec_number(2026): {nxt} (harusnya 49)')
if count != 48 or nxt != 49:
    print('  GAGAL: angka tidak sesuai. Restore backup bila perlu:')
    print(f'    cp {\"$BACKUP\"} db.sqlite3')
    raise SystemExit(1)
print('  SEMUA BERES: 48 EC mengalam dan nomor berikutnya 49.')
"
