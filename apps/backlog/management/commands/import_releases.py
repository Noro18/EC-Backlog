import csv
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.backlog.models import EC, Release

RELEASES_COLUMNS = {"year_release", "number_sequence_release", "go_live"}
MAP_COLUMNS = {"year", "number_sequence", "year_release", "number_sequence_release"}


def read_csv(path, expected_columns):
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        columns = set(reader.fieldnames or [])
        rows = list(reader)
    missing = sorted(expected_columns - columns)
    unknown = sorted(columns - expected_columns)
    if missing or unknown:
        parts = []
        if missing:
            parts.append(f"missing {', '.join(missing)}")
        if unknown:
            parts.append(f"unknown {', '.join(unknown)}")
        raise CommandError(f"refusing to import: bad header in {path.name} ({'; '.join(parts)})")
    return rows


def parse_go_live(text):
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return date.fromisoformat(stripped)
    except ValueError:
        return "invalid"


def positive_int(text):
    try:
        return int(text.strip())
    except ValueError:
        return None


def validate(rows_releases, rows_map):
    refusals = []

    seen_releases = set()
    for line_number, row in enumerate(rows_releases, start=2):
        year = positive_int(row["year_release"])
        number = positive_int(row["number_sequence_release"])
        if year is None or number is None:
            refusals.append(
                (f"releases line {line_number}", "year_release or number_sequence_release is invalid")
            )
            continue
        if parse_go_live(row["go_live"]) == "invalid":
            refusals.append((f"releases line {line_number}", f'go_live "{row["go_live"]}" is not an ISO date'))
        seen_releases.add((year, number))

    mapped_ec = {}
    for line_number, row in enumerate(rows_map, start=2):
        ec_year = positive_int(row["year"])
        ec_number = positive_int(row["number_sequence"])
        rel_year = positive_int(row["year_release"])
        rel_number = positive_int(row["number_sequence_release"])
        if None in (ec_year, ec_number, rel_year, rel_number):
            refusals.append((f"map line {line_number}", "one of the four fields is not a valid positive integer"))
            continue
        ec_key = (ec_year, ec_number)
        release_key = (rel_year, rel_number)
        if not EC.objects.filter(year=ec_year, number_sequence=ec_number).exists():
            refusals.append((f"map line {line_number}", f"EC ({ec_year},{ec_number}) does not exist in the database"))
        elif ec_key in mapped_ec and mapped_ec[ec_key] != release_key:
            refusals.append((f"map line {line_number}", f"EC ({ec_year},{ec_number}) is already mapped to another release"))
        else:
            mapped_ec[ec_key] = release_key
        if release_key not in seen_releases:
            refusals.append((f"map line {line_number}", f"release ({rel_year},{rel_number:03d}) is missing from the releases file"))

    for release_key in sorted(seen_releases):
        if Release.objects.filter(year=release_key[0], number_sequence=release_key[1]).exists():
            refusals.append(
                ("database", f"release {release_key[0]}-{release_key[1]:03d} already exists")
            )

    return refusals, seen_releases, mapped_ec


def build_releases(rows_releases, seen_releases, mapped_ec):
    dates = {}
    for row in rows_releases:
        key = (positive_int(row["year_release"]), positive_int(row["number_sequence_release"]))
        go_live = parse_go_live(row["go_live"])
        if isinstance(go_live, date) and (key not in dates or go_live > dates[key]):
            dates[key] = go_live

    releases = []
    for year, number in sorted(seen_releases):
        ec_keys = [ec_key for ec_key, rel_key in mapped_ec.items() if rel_key == (year, number)]
        statuses = [
            EC.objects.get(year=ec_year, number_sequence=ec_number).status
            for ec_year, ec_number in ec_keys
        ]
        is_open = True if not statuses else any(status != EC.Status.CLOSED for status in statuses)
        releases.append(
            Release(
                release_code=f"TT_ON_{year}-{number:03d}",
                year=year,
                number_sequence=number,
                is_open=is_open,
                production_go_live_date=dates.get((year, number)),
            )
        )
    return releases


class Command(BaseCommand):
    help = "RNF04 pass 2: import historical Releases and attach ECs. Dry-run unless --commit."

    def add_arguments(self, parser):
        parser.add_argument("releases_csv", type=str)
        parser.add_argument("map_csv", type=str)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        path_releases = Path(options["releases_csv"])
        path_map = Path(options["map_csv"])
        for path in (path_releases, path_map):
            if not path.exists():
                raise CommandError(f"File not found: {path}")
        rows_releases = read_csv(path_releases, RELEASES_COLUMNS)
        rows_map = read_csv(path_map, MAP_COLUMNS)
        if not rows_releases:
            raise CommandError("refusing to import: the releases file has no data rows")

        refusals, seen_releases, mapped_ec = validate(rows_releases, rows_map)

        lines = [
            (
                f"Releases file: {path_releases.name} ({len(rows_releases)} rows, "
                f"{len(seen_releases)} distinct releases)"
            ),
            f"Map file: {path_map.name} ({len(rows_map)} EC↔Release links)",
        ]
        if refusals:
            lines.append(f"Refused ({len(refusals)}):")
            lines.extend(f"  {source}: {reason}" for source, reason in refusals)
        self.stdout.write("\n".join(lines))

        if not options["commit"]:
            self.stdout.write("Dry-run only: nothing was written. Re-run with --commit to load.")
            return
        if refusals:
            details = "; ".join(f"{source}: {reason}" for source, reason in refusals)
            raise CommandError(f"refusing to import: {len(refusals)} issue(s) ({details})")

        with transaction.atomic():
            releases = build_releases(rows_releases, seen_releases, mapped_ec)
            Release.objects.bulk_create(releases)
            release_by_key = {(r.year, r.number_sequence): r for r in releases}
            attached = 0
            for ec_key, release_key in mapped_ec.items():
                attached += EC.objects.filter(year=ec_key[0], number_sequence=ec_key[1]).update(
                    release=release_by_key[release_key]
                )

        self.stdout.write(f"Imported {len(releases)} Release(s), attached {attached} EC(s).")
