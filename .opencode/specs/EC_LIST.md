# Spec: EC List Page (backlog)

## Objective

Wire `EClistView` so `/ec/` renders real EC rows from the database instead of the static stub.
Users can browse the backlog with pagination and column sorting.

- As a visitor, I see all ECs sorted newest first.
- As a visitor, I can sort by any column (EC ID, reference, release, status, created).
- As a visitor, I can paginate through the list.
- As a visitor, I can click "Ver" to open the EC detail URL (detail view wiring is **out of scope**).

**Out of scope:** filters (follow-up feature), authentication/permissions, detail view, create form.

## Tech Stack

Django 6.1, django-tables2, django-filter installed but unused here. Python via uv.

## Commands

```bash
uv run pytest apps/backlog/tests/test_views.py   # feature tests
uv run pytest                                     # full suite
uv run ruff check . && uv run ruff format .       # lint
uv run python manage.py runserver                 # manual check at /ec/
```

## Project Structure

```
apps/backlog/
├── selectors.py        # ec_list_queryset() — select_related/prefetch_related, ordering
├── tables.py           # ECTable (django-tables2)
├── views.py            # EClistView → FilterView or TemplateView with table context
└── tests/
    ├── test_views.py   # new tests
    └── factories.py    # existing ECFactory/ReleaseFactory/UserFactory
templates/backlog/
├── ec_list.html        # renders table via {% render_table table %}
```

## Code Style

Thin views; queryset logic in `selectors.py`. Line length 100, ruff-formatted.

```python
# selectors.py
def ec_list_queryset() -> QuerySet:
    return EC.objects.select_related(
        "requester", "responsible_cd", "release"
    ).order_by("-year", "-number_sequence")
```

## Testing Strategy

pytest-django + factory-boy, tests in `apps/backlog/tests/test_views.py` (TDD: failing test first).

1. GET `/ec/` returns 200.
2. Response contains a real EC created by `ECFactory` (its reference appears in content).
3. Table context present (`table` key), queryset has `select_related` applied (query count ≤ threshold, use `django.test.AssertNumQueries`).
4. Pagination: 25 per page; creating 30 ECs → second page reachable via `?page=2`.
5. Ordering default: newest (`-year`, `-number_sequence`) first.

## Boundaries

- **Always:** TDD (red → green → refactor), `uv run pytest` + ruff before done, thin views, business reads in `selectors.py`.
- **Ask first:** new dependencies, model/migration changes, auth requirements.
- **Never:** commit db/env files, write filters "while we're here", touch detail/create views.

## Success Criteria

- `/ec/` shows real DB rows with sortable headers and working pagination.
- All new tests pass; full `uv run pytest` green; ruff clean.
- No filters, no auth, no changes to other views.

## Open Questions

- None.
