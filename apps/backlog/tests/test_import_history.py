import csv
import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.backlog.models import EC
from apps.backlog.services import next_ec_number

pytestmark = pytest.mark.django_db


def write_csv(tmp_path, rows, header=None):
    header = header or ["year", "number_sequence", "reference", "description", "status"]
    path = tmp_path / "limpo.csv"
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_the_default_run_is_a_dry_run_and_writes_nothing(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": "Korreção", "status": "closed"},
    ])
    call_command("import_history", str(path))

    assert EC.objects.count() == 0


def test_commit_writes_ecs_with_is_imported_and_preserved_numbers(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "7",
         "reference": "RT2026001", "description": "Korreção", "status": "closed"},
    ])
    call_command("import_history", str(path), commit=True)

    ec = EC.objects.get()
    assert (ec.year, ec.number_sequence, ec.is_imported) == (2026, 7, True)


def test_an_unmapped_status_is_refused(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": "Korreção", "status": "wip"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 0


def test_a_blank_number_sequence_is_refused(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "",
         "reference": "CR2026001", "description": "Korreção", "status": "closed"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 0


def test_a_duplicate_inside_the_file_is_refused(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "7",
         "reference": "CR2026001", "description": "Korreção", "status": "closed"},
        {"year": "2026", "number_sequence": "7",
         "reference": "CR2026002", "description": "Korreção 2", "status": "closed"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 0


def test_a_row_colliding_with_an_existing_ec_is_refused(tmp_path):
    EC.objects.create(
        year=2026,
        number_sequence=7,
        reference="RT2026001",
        description="Already here",
        status="closed",
    )
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "7",
         "reference": "CR2026001", "description": "Korreção", "status": "closed"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 1
    assert EC.objects.first().reference == "RT2026001"


def test_accents_survive_the_round_trip(tmp_path):
    italian = "Alterações às Ofertas de Internet GPON - Fase 1"
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": italian, "status": "closed"},
    ])
    call_command("import_history", str(path), commit=True)

    assert EC.objects.get().description == italian


def test_is_open_rows_map_to_in_validation(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": "Korreção", "status": "is_open"},
    ])
    call_command("import_history", str(path), commit=True)

    assert EC.objects.get().status == EC.Status.IN_VALIDATION


def test_commit_is_all_or_nothing_when_one_row_is_bad(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": "OK", "status": "closed"},
        {"year": "2026", "number_sequence": "",
         "reference": "CR2026002", "description": "Broken", "status": "closed"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 0


def test_an_unknown_column_is_reported(tmp_path):
    rows = [
        {"year": "2026", "number_sequence": "1", "reference": "CR2026001",
         "description": "Korreção", "status": "closed", "go_live": "null"},
    ]
    path = write_csv(tmp_path, rows, header=[
        "year", "number_sequence", "reference", "description", "status", "go_live",
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path))

    assert EC.objects.count() == 0


def test_after_the_import_the_next_ec_number_is_free(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "7",
         "reference": "RT2026001", "description": "Korreção", "status": "closed"},
        {"year": "2026", "number_sequence": "12",
         "reference": "CR2026009", "description": "Korreção 2", "status": "closed"},
    ])
    call_command("import_history", str(path), commit=True)

    assert next_ec_number(2026) == 13


def test_a_blank_reference_is_refused(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "1",
         "reference": "CR2026001", "description": "Korreção", "status": "closed"},
        {"year": "2026", "number_sequence": "2",
         "reference": "", "description": "No ref", "status": "closed"},
    ])
    with pytest.raises(CommandError):
        call_command("import_history", str(path), commit=True)

    assert EC.objects.count() == 0


def test_the_report_shows_years_and_status_counts(tmp_path):
    path = write_csv(tmp_path, [
        {"year": "2026", "number_sequence": "7",
         "reference": "RT2026001", "description": "Korreção", "status": "closed"},
        {"year": "2026", "number_sequence": "8",
         "reference": "CR2026008", "description": "Korreção 2", "status": "is_open"},
    ])
    out = io.StringIO()
    call_command("import_history", str(path), stdout=out)

    text = out.getvalue()
    assert "Years: 2026..2026" in text
    assert "Status: closed=1, in_validation=1" in text
