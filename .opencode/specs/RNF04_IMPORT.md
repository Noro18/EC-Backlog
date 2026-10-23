# Spec — Historical import (RNF04)

## Objective

Load the existing 2019–2026 EC history into the system in **one deliberate pass**, keeping the
identifiers already assigned, without touching the workflow that governs live ECs.

- As an Administrator, I run the command **without `--commit`** and read a report of exactly what
  would be written (rows, per-status counts, refused rows with line numbers). Nothing changes.
- As an Administrator, I re-run it with `--commit` and the history appears in the EC list with its
  original `year` + `number_sequence` and `is_imported = True`.
- As a developer, when a row is refused I get the file line number and the reason, so the notebook
  (Transform) can be fixed instead of the database being patched.

> **Naming.** SRD RNF04 calls this *historical data migration*
> (`docs/System_requirements.md:194`); the design doc calls it *historical import*
> (`database-scheme.md §7.7`, line 312). This spec uses **historical import** for the code and
> **RNF04** when referring to the requirement.

## Assumptions

1. The **input is the cleaned file produced by the user's Jupyter notebook** — the notebook is the
   Transform step and lives **outside** this repository. This command is only the Load step.
2. The cleaned sample observed on 2026-10-23 has the columns
   `year, number_sequence, Referencia, Descrisaun, year_release, number_sequence_release, status,
   go_live`, where `number_sequence` is **empty**, `status` holds `Closed` / `is_open`, and
   `go_live` mixes ISO dates with the literal string `"null"`.
3. `django-import-export>=4.4.1` is already a dependency (`pyproject.toml:15`) and `"import_export"`
   is already in `INSTALLED_APPS` (`config/settings/base.py:53`). **No `openpyxl`** is installed.
4. Baseline on this branch (`feat/historical-import`, `upstream/main` = `1cab42c`, PR #73 merged):
   **242 tests green**.
5. `EC` is already shaped for legacy rows: `is_imported` (`apps/backlog/models.py:92`), nullable
   `requester` / `release` / `responsible_cd` (`:68,75,82`), nullable `creation_date` /
   `implemented_at` (`:89,91`), and `UNIQUE(year, number_sequence)` (`:98`).

## Decisions (proposed 2026-10-23)

1. **Transform owns parsing; Load owns validation.** The notebook must emit an **explicit
   `number_sequence`** column. The import never derives a number from the free-text reference:
   the sample shows non-uniform shapes (`CR2026003`, `COR2026001`, `RT202629411`), so a regex rule
   would silently produce wrong IDs — exactly what RNF04 forbids.
2. **v1 imports EC metadata only; `EC.release` stays NULL.** The historical release columns are
   unreliable (the `status` column already carries `is_open`, a `Release` flag) and Release has
   domain rules (capacity 10, auto-close, `production_go_live_date`) that history would violate.
   Attaching releases later is a separate pass — see *Deferred*.
3. **`--dry-run` is the default.** The command writes nothing unless `--commit` is passed. A
   migration command that writes by default is a footgun.
4. **All-or-nothing.** Any refused row aborts `--commit` before a single EC is written
   (`transaction.atomic` + `CommandError`). A half-imported history is worse than no import.
5. **`is_imported = True` on every row; `id` is never read from the file.** Identity is
   `(year, number_sequence)`, which is also the duplicate key checked twice: inside the file and
   against rows already in the database.
6. **Unmapped `status` = refused row, never guessed.** `Closed` maps to `closed`
   (case-insensitive after `strip()`); `is_open` currently has **no mapping** and is therefore
   refused. Writing status directly is the one documented exception to "status only through
   workflow" (`database-scheme.md:19`), so the mapping must be explicit and visible.
7. **CSV by default.** The stdlib `csv` module needs no new dependency. XLSX support is only added
   (`uv add "django-import-export[xlsx]"`) if the notebook cannot emit CSV — an open question.
8. **Strict column contract.** Extra or misspelled columns are an error, not silently ignored,
   because a renamed column that is skipped turns into a column of NULLs.
9. **The notebook stays out of the repository.** Its cleaning rules are stated in this spec
   (Input) so the result is reproducible; the notebook itself is not committed.

## Tech Stack

Django 6.1, `django-import-export` (already installed) for the `ModelResource` mapping, stdlib
`csv` for reading, `factory-boy` for tests.
**No new dependency** for the CSV path.

## Commands

```bash
# dry-run (default): report only, zero writes
uv run python manage.py import_history /path/limpo.csv

# real import
uv run python manage.py import_history /path/limpo.csv --commit

# checks
uv run pytest apps/backlog/tests/test_import_history.py -q
uv run pytest -q                       # 242 -> 252
uv run ruff check .
```

> `uv run ruff format .` is not part of the done-check (pre-existing files are unformatted).

## System Architecture

```
apps/backlog/
├── resources.py                              # NEW  ECResource — column <-> field mapping only
├── management/
│   ├── __init__.py                           # NEW  (empty)
│   └── commands/
│       ├── __init__.py                       # NEW  (empty)
│       └── import_history.py                 # NEW  read -> validate -> report -> (commit)
└── tests/
    └── test_import_history.py                # NEW  TDD: dry-run, commit, refusals, next number

.opencode/specs/RNF04_IMPORT.md               # this file
```

**Import direction** stays legal: everything lives in `apps/backlog` and imports only Django,
`import_export`, and its own modules. Nothing imports `workflow`.

**Documented deviation from §5.** `ARCHITECTURE.md` puts business logic in `services.py`; this is a
one-off infrastructure job, not domain behaviour. `database-scheme.md §7.7` places it in
`resources.py` + a management command, and that is what this spec follows — the import writes
`status` directly (the documented exception) and never calls a `workflow` service.

## Database Schema Changes

**None.** No model edit, no migration, no constraint.
The uniqueness that protects the import already exists: `UNIQUE(year, number_sequence)`
(`apps/backlog/models.py:98`).

## Input / Output

**Input file contract** (UTF-8, comma-separated, header row, exactly these five columns):

```csv
year,number_sequence,reference,description,status
2026,3,CR2026003,"Alterações nas Ofertas de Internet GPON - Fase 1",closed
```

| Column | Required | Rule |
|---|---|---|
| `year` | yes | 4-digit calendar year, must equal the year inside the EC identity |
| `number_sequence` | yes | positive integer; **blank or 0 = refused** (never minted from thin air) |
| `reference` | yes | non-empty, ≤ 50 chars (`EC.reference`) |
| `description` | yes | non-empty (`EC.description`, `blank=False`) |
| `status` | yes | one of the six `EC.Status` values after mapping (below) |

**Status mapping** — the only values allowed to enter `EC.status`:

| Source (after `strip().lower()`) | Target |
|---|---|
| `closed` | `closed` |
| `in_validation` / `in validation` | `in_validation` |
| `approved` | `approved` |
| `rejected` | `rejected` |
| `sent_to_des` / `sent to des` | `sent_to_des` |
| `cancelled` / `canceled` | `cancelled` |
| **anything else** (today: `is_open`) | **refused** — reported, never guessed |

**CLI behaviour:**

| Invocation | Writes | Exit code |
|---|---|---|
| no flag (dry-run), no refusals | 0 rows | 0 |
| no flag (dry-run), with refusals | 0 rows | 0 (report only) |
| `--commit`, no refusals | all rows | 0 |
| `--commit`, any refusal | **0 rows** | non-zero (`CommandError`) |
| file missing / bad header | 0 rows | non-zero |

**Report format** (stdout, dry-run and commit alike):

```
File: limpo.csv (312 rows)
Years: 2019..2026
Status: closed=287, in_validation=11, sent_to_des=8, approved=6
Refused (3):
  line  42: status "is_open" has no mapping
  line 118: number_sequence is blank
  line 260: duplicate (2026, 12) already in the file
Dry-run only: nothing was written. Re-run with --commit to load.
```

## Edge Cases

1. **Blank or zero `number_sequence`** → refused. RNF04 is about *preserving* identifiers; minting
   a new number would silently rewrite history.
2. **Duplicate `(year, number_sequence)` inside the file** → refused, both line numbers reported.
3. **Row colliding with an EC already in the database** → refused, so a second run over a live
   system cannot overwrite (or duplicate) a real EC.
4. **Unknown status** (today: `is_open`) → refused. The fix belongs in the notebook, not in code.
5. **`"null"` as a date string** → `go_live` is not part of this contract; if a date column is
   included later, the notebook must emit an empty cell, not the text `null`.
6. **Unknown / misspelled / extra column** → the command names the offending columns and writes
   nothing; the notebook must select exactly the five columns.
7. **Empty file (header only)** → refused with a clear message, not a silent success.
8. **Accented Portuguese text** — e.g. `Alterações`, `Correção` — must round-trip unchanged
   (UTF-8, `csv` handles quoting).
9. **Very long descriptions** → accepted (`TextField`); only `reference` has a 50-char limit.
10. **Year range** — no rule is invented here. The report prints `min..max` year so a human can
    spot a corrupted year before committing.
11. **Order of writes** — within one `transaction.atomic()`; a crash mid-file leaves zero rows.

## Project Structure

See *System Architecture*. Four new files (two of them empty package markers), one new test module,
no template, no view, no URL, no migration.

## Code Style

```python
# resources.py — mapping only; no validation, no reporting
class ECResource(resources.ModelResource):
    class Meta:
        model = EC
        fields = ("year", "number_sequence", "reference", "description", "status")
        import_id_fields = ("year", "number_sequence")   # identity, never `id`
        skip_unchanged = True
        report_skipped = True

    def before_save_instance(self, instance, row, **kwargs):
        instance.is_imported = True
        instance.requester = None          # §7.7: history has no owner in-app
        instance.responsible_cd = None
        instance.creation_date = None
```

```python
# management/commands/import_history.py — orchestration only
class Command(BaseCommand):
    help = "RNF04: load the cleaned historical export. Dry-run unless --commit."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        rows = read_rows(options["path"])          # header contract enforced here
        accepted, refused = validate(rows)         # pure + one DB query for collisions
        self.stdout.write(report(rows, accepted, refused))
        if not options["commit"]:
            return                                 # dry-run: nothing was written
        if refused:
            raise CommandError(f"refusing to import: {len(refused)} row(s) rejected")
        with transaction.atomic():
            load(accepted)
```

## Testing Strategy

TDD: failing test first. New module `apps/backlog/tests/test_import_history.py`, same
`pytestmark = pytest.mark.django_db` + `class Test...:` style, CSV fixtures built in `tmp_path`.

| # | Test | Proves |
|---|------|--------|
| 1 | `test_the_default_run_is_a_dry_run_and_writes_nothing` | Decision 3 |
| 2 | `test_commit_writes_ecs_with_is_imported_and_preserved_numbers` | RNF04 core |
| 3 | `test_accents_survive_the_round_trip` | edge case 8 |
| 4 | `test_a_blank_number_sequence_is_refused` | edge case 1 |
| 5 | `test_a_duplicate_inside_the_file_is_refused` | edge case 2 |
| 6 | `test_a_row_colliding_with_an_existing_ec_is_refused` | edge case 3 |
| 7 | `test_an_unmapped_status_is_refused` (`is_open`) | Decision 6 |
| 8 | `test_commit_is_all_or_nothing_when_one_row_is_bad` | Decision 4 |
| 9 | `test_an_unknown_column_is_reported` | Decision 8 |
| 10 | `test_after_the_import_the_next_ec_number_is_free` (`next_ec_number(2026)`) | no collision |

Expected suite: **252 = 242 + 10**.

## Boundaries

- **Always:** TDD, `uv run pytest -q` + `uv run ruff check .` before done, CSV contract enforced,
  PT UI strings untouched, no invented status values.
- **Ask first:** XLSX support (adds `openpyxl`), importing Releases or `production_go_live_date`,
  matching `requester`/`responsible_cd` to real accounts, attaching historical documents, any
  change to `accounts.User`, re-running the import over production data.
- **Never:** a migration or model change, setting `id`, deriving `number_sequence` from free text,
  calling a `workflow` service, touching templates/views/urls, committing the notebook or the
  source Excel, `git add .` over the untracked `apps/workflow/management/*` files.

## Success Criteria

- [ ] `import_history <file>` (no flag) prints the report and leaves both tables untouched.
- [ ] `--commit` loads every accepted row with `is_imported=True`, the original
      `year`/`number_sequence`, and a mapped status.
- [ ] Accented Portuguese text is stored exactly as in the file.
- [ ] Any refused row aborts `--commit` with a non-zero exit and **zero** rows written.
- [ ] `is_open` is refused, not translated, until a mapping decision is recorded here.
- [ ] `next_ec_number(2026)` after the import equals `max(imported) + 1`.
- [ ] 252 tests green, `ruff check .` clean, no migration generated.

## Deferred

- **Releases and go-live dates** — the second pass: create `Release` rows from
  `year_release` + `number_sequence_release` (`TT_ON_YYYY-NNN`), set
  `production_go_live_date`, then attach imported ECs. Needs its own decisions (capacity, `is_open`
  for history).
- **Documents** for historical ECs (attach first `DocumentVersion` when a file exists).
- **`requester` / `responsible_cd`** matching from name columns to real accounts.
- **XLSX input**, if CSV is not workable.
- **A UI** for the import (upload page) — §7.7 keeps it CLI-only.

## Open Questions

- **Exact `status` values across the whole file.** Only `Closed` and `is_open` were seen in the
  sample. Needs `df["status"].value_counts(dropna=False)` before the mapping table can be closed.
- **Where the real EC status went.** `is_open` is a Release flag; if the EC status was lost in the
  merge, the notebook must recover it from the source sheet — code cannot invent it.
- **How `number_sequence` is derived** (which reference patterns are valid, how `RT202629411` is
  read). Transform-side decision, validated by the dry-run.
- **CSV or XLSX** as the notebook's output.
- **Whether historical Releases are wanted at all** (Deferred item 1), and who owns that decision.

## Branch Name

`feat/historical-import`
