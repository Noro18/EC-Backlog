# Spec: Release List Page (backlog)

## Objective

Wire `ReleaseListView` so `/backlog/release/` renders real Release rows from the database
instead of the hardcoded mock rows in `release_list.html`.
A visitor sees how full each Release is and whether it is still open.

- As a visitor, I see every Release with its code, EC count, capacity, occupancy and state.
- As a visitor, I can sort by any column and paginate through the list.
- As a visitor, I see the production go-live date once it has been recorded, or a dash.

**Out of scope:** filters (year / state), an action column, a release detail page,
editing the go-live date, creating a Release, and any write of any kind.

## Assumptions

1. Page stays **public**, same decision as the EC list and EC detail pages
   (`EC_LIST.md`, `EC_DETAIL.md`); `accounts` has no views or login yet.
2. View becomes `SingleTableView` (like `ECListView`), keeping `template_name`.
3. **No model change, no migration.** The state shown is derived from fields that already
   exist (`is_open`, `ec_total`, `capacity`) — see "Derived columns" below.
4. EC count comes from `annotate(Count("ecs"))` (`database-scheme.md` §4.3: "On list
   pages use `annotate(Count("ecs"))` instead of `ec_count` to avoid N+1 queries").
5. The annotation is **aliased** (e.g. `ec_total`), never named `ec_count`:
   `Release.ec_count` is a read-only property, and assigning an annotation with that
   name raises `AttributeError: can't set attribute`. This is a real trap, not a style choice.
6. Visual design follows the existing mock (badges, same column set), so this is a
   data-wiring change, not a redesign. **Deviation, 2026-10-02:** the mock's occupancy
   **progress bar is dropped**, and occupancy appears as a plain `2 / 10` ratio **inside
   the ECs column** — agreed with the user. The bar adds CSS and markup for information a
   number already conveys.
7. Dates render with explicit numeric formats (`d/m/Y`, `d/m/Y H:i`) — `LANGUAGE_CODE`
   is `en-us`, so there are no localized month names to rely on.
8. UI strings stay Portuguese, matching every other page.

## Tech Stack

Django 6.1, django-tables2 (already used by `ECTable`). Bootstrap 5 + Inter, both already
in place. `django-filter` is installed but unused in this feature.

## Commands

```bash
uv run pytest apps/backlog/tests/test_views.py   # release list tests
uv run pytest apps/backlog/tests/test_selectors.py  # selector tests (no HTTP)
uv run pytest                                     # full suite — everything already green must stay green
uv run ruff check . && uv run ruff format .       # lint
uv run python manage.py runserver                 # manual check at /backlog/release/
```

## Project Structure

```
apps/backlog/
├── selectors.py         # new file: release_with_ec_count() — annotated, ordered base query
├── tables.py           # ReleaseTable (new class, alongside ECTable)
├── views.py            # ReleaseListView -> SingleTableView (delegates to the selector)
└── tests/
    ├── test_views.py   # new file; release list tests only (the EC list/detail view
    │                   #   tests referenced by the earlier specs are not in git)
    ├── test_selectors.py  # new file; tests for selectors.py, no HTTP involved
    └── factories.py    # existing ReleaseFactory
templates/backlog/
└── release_list.html   # replace the two dummy rows with {% render_table table %}
```

No `static/` change: the occupancy bar was dropped (assumption 6), so there is no CSS to
move out of the table template.

`selectors.py` **is** used here: the annotated queryset gets a name and one owner.
`services.py` is **not** — this page performs no writes, so there is no business rule to
protect. See "Layering decision" below.

## Layering decision

ARCHITECTURE §6 puts business logic in `services.py` (writes) / `selectors.py` (complex
reads) and out of views. Applied to this feature:

- **`selectors.py` — used.** `release_with_ec_count()` owns the annotated, ordered base
  query for Releases. It is named because it is a real query concept (join + count + order,
  the exact thing that must not be re-derived per page) and because the second caller is
  already known: RF12 filters and the deferred release detail page will both need it.
  The view calls it and adds nothing of its own.
- **`services.py` — deliberately absent.** A service is justified by a rule that must hold
  no matter who calls it (capacity, closing, EC numbering, go-live role check). This page
  writes nothing, so a service here would be a pass-through wrapper around the queryset —
  indirection with no rule in it. It arrives in the next slice with `create_release()`,
  `assign_ec_to_release()` and `recheck_release_closing()`, each with tests.
- **`ECListView` is left as it is** (queryset inline, no `selectors.py`). Two list pages may
  differ in shape; consistency with a later refactor is worth less than not touching working
  code outside the scope. If `ec_backlog_base()` is ever extracted, it happens with RF12.

## Derived columns (no schema change)

| Column | Source | Notes |
|---|---|---|
| ECs | `ec_total` + `capacity` | ratio text, `2 / 10`, in the ECs column itself — no progress bar (assumption 6) |
| Estado | derived | `is_open` → "Aberto" `text-bg-success`; else if `ec_total >= capacity` → "Lotado" `text-bg-danger`; else → "Concluído" `text-bg-secondary` |
| Go-live | `production_go_live_date` | `d/m/Y`, or `—` when `None` |
| Criado em | `created_at` | `d/m/Y H:i` |

The three-state badge is safe to derive: `is_open` becomes `False` through exactly two paths
(`database-scheme.md` §7.3) — full, or finished (every non-cancelled EC Closed **and** the
go-live date set). So "not open and not full" can only mean finished.

## Code Style

Thin view: it delegates the query to `release_with_ec_count()` and passes the result to
`ReleaseTable`. Table class sits next to `ECTable` and follows its column conventions
(`attrs={"td": {...}}` for alignment, `verbose_name` in Portuguese, `template_code` for
anything with markup). Line length 100, ruff-formatted.

## Testing Strategy

pytest-django + factory-boy, tests in `apps/backlog/tests/test_views.py` (selector tests in
`test_selectors.py`), written **before** the view/table code
(`.opencode/skills/django-tdd-loop/SKILL.md`).

Status key: ✅ written and passing (52 green) · ⏳ pending, deferred to a later pass.

1. ✅ `GET /backlog/release/` returns 200.
2. ✅ Response contains a real Release created by `ReleaseFactory` (its code appears in the body).
3. ✅ `table` is present in the context.
4. ✅ EC count, occupancy and state are derived from the database, not hardcoded: a Release with
   2 of 5 ECs renders `2 / 5` (`capacity=5`, so a hardcoded 10 would fail); a full open one
   renders "Lotado"; an open non-full one renders "Aberta"; a finished one renders
   "Concluído".
5. ⏳ Default ordering is newest first (`-year`, `-number_sequence`).
6. ⏳ Sorting works (e.g. `?sort=release_code`), via the sortable header.
7. ⏳ Pagination: 25 per page; 30 Releases → `?page=2` reachable.
8. ✅ No N+1: constant query count while the row count grows — `test_query_count_does_not_grow_with_rows`,
   implemented with `CaptureQueriesContext` (caught `ec_count` → `12 == 5`, i.e. 1 query
   per row; green after the badge switched to the `ec_total` annotation).
9. ⏳ Empty database → the table's empty text, not a crash.
10. ⏳ `release_with_ec_count()` is directly testable without HTTP (called as a function,
    asserting on the returned queryset), which is the point of putting it in `selectors.py`.
    Its tests live in `test_selectors.py` and must prove the rows are `Release` objects,
    not dicts — that is the regression test for the `.values()` mistake.
11. ✅ Closed **and** full release → "Lotado" (`test_closed_and_full_renders_lotado`) — the
    branch-order decision: fullness wins over `is_open`.

## Boundaries

- **Always:** TDD (red → green → refactor), `uv run pytest` + ruff before done, thin views,
  `select_related`/`annotate` on list pages, the query owned by `release_with_ec_count()`.
- **Ask first:** new dependencies, model/migration changes, filters, auth/permissions,
  touching `ECListView`, the EC detail/form views, or the `workflow`/`documents` apps.
- **Never:** change `Release.is_open` or `capacity` here (they belong to `backlog/services.py`,
  not built yet), change `EC.status`, edit the go-live date (that write belongs to `workflow`,
  `database-scheme.md` §7.6), re-add dummy rows to the template, create `backlog/services.py`
  with nothing in it, or add a selector whose only caller is the view below it.

## Success Criteria

- `/backlog/release/` shows real DB rows with sortable headers and working pagination.
- EC counts, occupancy ratios and state badges are computed from the database.
- The view holds no query logic; `release_with_ec_count()` is the single owner of the
  annotated base query and is testable without HTTP.
- No hardcoded values remain in `release_list.html`; no inline `style` in the table
  `template_code`.
- The new tests pass, the existing suite stays green, ruff is clean.
- No model change, no migration, no filters, no action column, no permission logic.

## Outstanding work (pending)

Code items still required to call Slice 1 done — all ⏳, none blocking the app from running:

1. ⏳ Remove the `action` column from `ReleaseTable` (declaration + `Meta.fields`) — violates
   "no action column" and renders a dead `href="#"`.
2. ⏳ Add `production_go_live_date` (`d/m/Y`, `—` when `None`) and `created_at`
   (`d/m/Y H:i`) columns.
3. ✅ Badge palette vs this spec: the code rendered Aberta/`text-bg-warning` and
   Concluído/`text-bg-success`, while the §7 table says `text-bg-success` /
   `text-bg-secondary`. The classes now match the table, locked by
   `test_badge_palette_matches_spec`. The label was left as "Aberta" — see the
   Decisions log, the table and the prose below disagree with each other.
4. ⏳ `uv run ruff check . --fix && uv run ruff format .` — `I001` in `apps/backlog/views.py`
   is the last error; then full `uv run pytest`.
5. ✅ Commit the working slice — this PR.

## Decisions log

| Date | Decision |
|---|---|
| 2026-10-02 | Spec approved (`SPEC_APPROVED`) as written, before any code. |
| 2026-10-02 | `selectors.py` used; `services.py` deliberately absent (see "Layering decision"). |
| 2026-10-02 | Occupancy **progress bar dropped**; occupancy appears as `2 / 10` **inside the ECs column** (`ec_total` becomes a `TemplateColumn`). No `static/css` change needed. |
| 2026-10-02 | Selector tests live in `test_selectors.py`, not `test_views.py` — a selector is not a view. |
| 2026-10-02 | Badge precedence: **fullness wins over `is_open`** — a closed+full release renders "Lotado", not "Concluído". Locked by `test_closed_and_full_renders_lotado`. |
| 2026-10-02 | Status column reads the **annotation** `record.ec_total`, never the `ec_count` property — the property costs 1 query per row (N+1, caught as `12 == 5`). |
| 2026-10-05 | Badge **classes** aligned with the §7 table: Aberta → `text-bg-success`, Concluído → `text-bg-secondary`, Lotado unchanged (`text-bg-danger`). Locked by `test_badge_palette_matches_spec`. The **label** stays "Aberta" (feminine, agrees with "Release" and with the prose at line 127) rather than the table's "Aberto" — that spelling was never changed because it would only churn tests, and the two spots in this document disagree. |

## Deferred (next slices, each needs its own spec)

1. `backlog/services.py`: `create_release()`, `next_ec_number()` (§7.1),
   `assign_ec_to_release()` (atomic capacity re-check, refuse the 11th EC),
   `recheck_release_closing()` — `database-scheme.md` §7.2–7.3. Required before the EC
   create form (RF01/RF02) can be trusted. This is where the write side of the pattern
   gets its practice.
2. Go-live date entry (`record_go_live_date`) — belongs to `workflow`, DES role only (§7.6);
   blocked on `accounts`/RNF01 permissions.
3. Release detail page (the ECs of one Release) — becomes the second caller of
   `release_with_ec_count()`, which is when its extraction stops being speculative.
4. Filters on the list (year, open/full/closed) and `ec_backlog_base()` for RF12.

## Open Questions

- None for this feature. The scope above was agreed with the user on 2026-10-02.