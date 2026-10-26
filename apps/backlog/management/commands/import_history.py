import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.backlog.models import EC

STATUS_MAPPING = {
    "closed": "closed",
    "in_validation": "in_validation",
    "in validation": "in_validation",
    "approved": "approved",
    "rejected": "rejected",
    "sent_to_des": "sent_to_des",
    "sent to des": "sent_to_des",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "is_open": "in_validation",
}

EXPECTED_COLUMNS = {"year", "number_sequence", "reference", "description", "status"}


def valid_number(text):
    try:
        return int(text.strip()) > 0
    except ValueError:
        return False


def read_rows(path):
    """Read the CSV and enforce the strict column contract (Decision 8)."""
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        rows = list(reader)
    missing = sorted(EXPECTED_COLUMNS - columns)
    unknown = sorted(columns - EXPECTED_COLUMNS)
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown {', '.join(unknown)}")
        raise CommandError(f"refusing to import: bad header ({'; '.join(parts)})")
    return rows


def validate(rows):
    """Return a list of (line_number, reason) — collect everything, decide once."""
    refusals = []
    for line_number, row in enumerate(rows, start=2):
        source = row["status"].strip().lower()
        if source not in STATUS_MAPPING:
            refusals.append((line_number, f'status "{source}" has no mapping'))
        elif not valid_number(row["number_sequence"]):
            refusals.append((line_number, "number_sequence is blank, zero or not a number"))
        if not row["reference"].strip():
            refusals.append((line_number, "reference is blank"))

    seen = set()
    for line_number, row in enumerate(rows, start=2):
        key = (row["year"].strip(), row["number_sequence"].strip())
        if key in seen:
            refusals.append((line_number, "duplicate (year, number_sequence) in this file"))
        seen.add(key)

    for line_number, row in enumerate(rows, start=2):
        if not valid_number(row["number_sequence"]):
            continue
        if EC.objects.filter(
            year=int(row["year"]), number_sequence=int(row["number_sequence"])
        ).exists():
            refusals.append(
                (line_number, "(year, number_sequence) already exists in the database")
            )
    return refusals


def report(path, rows, refusals):
    counts = Counter(
        STATUS_MAPPING.get(row["status"].strip().lower(), "unmapped") for row in rows
    )
    years = sorted({int(row["year"]) for row in rows})
    lines = [f"File: {path.name} ({len(rows)} rows)"]
    lines.append(f"Years: {years[0]}..{years[-1]}")
    lines.append("Status: " + ", ".join(f"{k}={n}" for k, n in sorted(counts.items())))
    if refusals:
        lines.append(f"Refused ({len(refusals)}):")
        lines.extend(f"  line {n}: {reason}" for n, reason in refusals)
    return "\n".join(lines)


class Command(BaseCommand):
    help = "RNF04: load the cleaned historical export. Dry-run unless --commit."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["csv_path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        rows = read_rows(path)
        if not rows:
            raise CommandError("refusing to import: the file has no data rows")

        refusals = validate(rows)
        self.stdout.write(report(path, rows, refusals))

        if not options["commit"]:
            self.stdout.write("Dry-run only: nothing was written. Re-run with --commit to load.")
            return
        if refusals:
            details = "; ".join(f"line {n}: {reason}" for n, reason in refusals)
            raise CommandError(f"refusing to import: {len(refusals)} row(s) rejected ({details})")

        with transaction.atomic():
            for row in rows:
                EC.objects.create(
                    year=int(row["year"]),
                    number_sequence=int(row["number_sequence"]),
                    reference=row["reference"].strip(),
                    description=row["description"].strip(),
                    status=STATUS_MAPPING[row["status"].strip().lower()],
                    is_imported=True,
                )
        self.stdout.write(f"Imported {len(rows)} EC(s)")
