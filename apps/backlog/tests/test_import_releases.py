import csv

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.backlog.models import EC, Release
from apps.backlog.tests.factories import ECFactory

pytestmark = pytest.mark.django_db


def write_releases_csv(tmp_path, rows):
    header = ["year_release", "number_sequence_release", "go_live"]
    path = tmp_path / "releases_clean.csv"
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_map_csv(tmp_path, rows):
    header = ["year", "number_sequence", "year_release", "number_sequence_release"]
    path = tmp_path / "ec_release_map.csv"
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


def make_ecs(year, numbers, status):
    return [
        ECFactory(
            year=year, number_sequence=n, reference=f"REF{n}", status=status, release=None
        )
        for n in numbers
    ]


def test_the_default_run_is_a_dry_run_and_writes_nothing(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": "2026-01-23"},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "001"},
    ])
    call_command("import_releases", str(releases), str(mapping))

    assert Release.objects.count() == 0


def test_commit_creates_a_release_with_code_and_go_live(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": "2026-01-23"},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "001"},
    ])
    make_ecs(2026, [1], EC.Status.CLOSED)
    call_command("import_releases", str(releases), str(mapping), commit=True)

    release = Release.objects.get()
    assert release.release_code == "TT_ON_2026-001"
    assert (release.year, release.number_sequence) == (2026, 1)
    assert release.production_go_live_date.isoformat() == "2026-01-23"


def test_the_latest_go_live_wins(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "004", "go_live": ""},
        {"year_release": "2026", "number_sequence_release": "004", "go_live": "2026-02-13"},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "004"},
    ])
    make_ecs(2026, [1], EC.Status.CLOSED)
    call_command("import_releases", str(releases), str(mapping), commit=True)

    release = Release.objects.get()
    assert release.release_code == "TT_ON_2026-004"
    assert release.production_go_live_date.isoformat() == "2026-02-13"


def test_a_release_without_go_live_stays_open_without_date(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "003", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "003"},
    ])
    make_ecs(2026, [1], EC.Status.IN_VALIDATION)
    call_command("import_releases", str(releases), str(mapping), commit=True)

    release = Release.objects.get()
    assert release.production_go_live_date is None
    assert release.is_open is True


def test_a_release_whose_ecs_are_all_closed_is_not_open(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": "2026-01-23"},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "5",
         "year_release": "2026", "number_sequence_release": "001"},
        {"year": "2026", "number_sequence": "6",
         "year_release": "2026", "number_sequence_release": "001"},
    ])
    make_ecs(2026, [5, 6], EC.Status.CLOSED)
    call_command("import_releases", str(releases), str(mapping), commit=True)

    assert Release.objects.get().is_open is False


def test_capacity_is_not_enforced_for_history(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": str(n),
         "year_release": "2026", "number_sequence_release": "001"}
        for n in range(1, 13)
    ])
    make_ecs(2026, range(1, 13), EC.Status.CLOSED)
    call_command("import_releases", str(releases), str(mapping), commit=True)

    release = Release.objects.get()
    assert release.ecs.count() == 12 > release.capacity


def test_a_map_row_pointing_to_a_missing_ec_is_refused(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "99",
         "year_release": "2026", "number_sequence_release": "001"},
    ])
    with pytest.raises(CommandError):
        call_command("import_releases", str(releases), str(mapping), commit=True)

    assert Release.objects.count() == 0


def test_an_ec_mapped_to_two_releases_is_refused(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": ""},
        {"year_release": "2026", "number_sequence_release": "002", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "001"},
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "002"},
    ])
    make_ecs(2026, [1], EC.Status.CLOSED)
    with pytest.raises(CommandError):
        call_command("import_releases", str(releases), str(mapping), commit=True)

    assert Release.objects.count() == 0


def test_commit_attaches_ecs_and_leaves_unmapped_ones_null(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "001"},
        {"year": "2026", "number_sequence": "2",
         "year_release": "2026", "number_sequence_release": "001"},
    ])
    make_ecs(2026, [1, 2], EC.Status.CLOSED)
    ECFactory(
        year=2026, number_sequence=99, reference="REF99", status=EC.Status.CLOSED, release=None
    )
    call_command("import_releases", str(releases), str(mapping), commit=True)

    assert EC.objects.get(number_sequence=1).release.release_code == "TT_ON_2026-001"
    assert EC.objects.get(number_sequence=2).release.release_code == "TT_ON_2026-001"
    assert EC.objects.get(number_sequence=99).release is None


def test_a_map_referring_to_a_release_missing_from_the_file_is_refused(tmp_path):
    releases = write_releases_csv(tmp_path, [
        {"year_release": "2026", "number_sequence_release": "001", "go_live": ""},
    ])
    mapping = write_map_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "year_release": "2026", "number_sequence_release": "009"},
    ])
    make_ecs(2026, [1], EC.Status.CLOSED)
    with pytest.raises(CommandError):
        call_command("import_releases", str(releases), str(mapping), commit=True)

    assert Release.objects.count() == 0
