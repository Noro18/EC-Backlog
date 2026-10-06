# Spec — Dashboard Overview

## Objective

Add a single overview page at `/dashboard/` so users stop opening the EC list and the release list
one by one just to know where the backlog stands. Today the sidebar item "Painel" renders
`href="#"` (`base.html:25`), so the menu is dead.

- As a logged-in user, I open `/dashboard/` and see the headline numbers of the backlog.
- As a logged-in user, I see how many ECs sit in each status.
- As a logged-in user, I compare ECs used against the capacity of every release.
- As a logged-in user, I see how many ECs were created per month.
- As an anonymous visitor, I am redirected to the login page.

**Out of scope:** date-range filters, export to PDF/CSV, a public JSON API, per-user charts,
changing any EC status (that stays inside `workflow` services), and caching.

## Tech Stack

Django 6.1, Chart.js **vendored** under `static/vendor/chartjs/` (the repo never uses a CDN — see
`static/vendor/bootstrap/`, `static/vendor/htmx/`). No new Python dependency, no npm, no build step.

## Commands

```bash
uv run pytest apps/backlog/tests/test_dashboard.py   # feature tests
uv run pytest                                       # full suite
uv run ruff check .                                 # lint
uv run python manage.py check                       # routes wired
uv run python manage.py runserver                   # manual check at /dashboard/
```

> `uv run ruff format .` is **not** part of the done-check right now: 5 pre-existing files are
> already unformatted, so it fails regardless of this work. Run `ruff check .` instead.

## System Architecture

```
apps/backlog/
├── selectors.py            # EXTEND: dashboard_stats() — every query lives here
├── views.py                # ADD: DashboardView (thin: one selector call, one context key)
├── urls.py                 # ADD: path("dashboard/", ..., name="dashboard")
└── tests/
    └── test_dashboard.py   # NEW

templates/
├── base.html               # EDIT: point the existing "Painel" item at backlog:dashboard
└── backlog/
    └── dashboard.html      # NEW — cards + 3 <canvas> + json_script payloads

static/vendor/chartjs/
└── chart.umd.min.js        # NEW — vendored Chart.js build
```

Import direction is unchanged: `dashboard.html` and `DashboardView` only reach into
`apps.backlog`. No upward imports, no new app (§5).

## Database Schema Changes

**None.** Every number comes from existing columns: `EC.status`, `EC.creation_date`,
`Release.capacity`, `Release.is_open` and the `EC.release` relation.

## Input / Output

The view must not contain a query. `apps/backlog/selectors.py` exposes one function:

```python
def dashboard_stats() -> dict: ...
```

Contract:

| Key | Type | Meaning |
|-----|------|---------|
| `ec_total` | `int` | total number of ECs |
| `ec_by_status` | `dict[str, int]` | **every** status in `EC.Status` → count (missing statuses are `0`, so the donut never drops a slice) |
| `ec_open` | `int` | shorthand for `ec_by_status["in_validation"]` |
| `releases` | `list[dict]` | `release_code`, `capacity`, `ec_count`, `percent` — same source as `release_with_ec_count()` so the numbers match the release list |
| `releases_open` | `int` | `Release.objects.filter(is_open=True).count()` |
| `ec_by_month` | `list[dict]` | `{"month": "2026-08", "count": N}` ascending; rows with `creation_date` NULL are excluded |

Python → browser goes through the `json_script` filter (XSS-safe). Chart labels are translated to
Portuguese **in the template**, keeping presentation text out of the selector.

## Edge Cases

1. Anonymous request → `302` to `LOGIN_URL` (`/?next=/dashboard/`).
2. A status with zero rows still appears in `ec_by_status` (value `0`).
3. `Release.capacity == 0` → `percent` must be `0`, never a division-by-zero error.
4. `EC.creation_date` is NULL (historical imports) → excluded from `ec_by_month`.
5. No ECs and no releases at all → the page renders `200` with empty charts, no crash.
6. `releases` must reuse `release_with_ec_count()`, otherwise the dashboard and the release list
   would disagree on occupancy.

## Project Structure

No file moves. Only the files listed in *System Architecture* are touched.

## Code Style

```python
# selectors.py — all queries, plain dict in / plain dict out
def dashboard_stats() -> dict:
    status_rows = EC.objects.values("status").annotate(n=Count("id"))
    ...

# views.py — thin: no ORM call, no aggregation, no formatting
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "backlog/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = dashboard_stats()
        return context
```

Chart.js stays in `{% block extra_js %}`; card/chart markup in `{% block content %}`.

## Testing Strategy

Red → green → refactor. Tests live in `apps/backlog/tests/test_dashboard.py` and follow the
`pytestmark = pytest.mark.django_db` + `class Test...:` style used by `test_views.py`.

| # | Test | Proves |
|---|------|--------|
| 1 | `test_requires_login` | anonymous gets `302` |
| 2 | `test_returns_200_with_stats` | page opens, `stats` is in the context |
| 3 | `test_status_counts_include_zero_for_missing_statuses` | counts are complete, zeros included |
| 4 | `test_release_occupancy_matches_ec_count` | 2 ECs in a capacity-5 release → `ec_count == 2`, `percent == 40` |
| 5 | `test_monthly_series_uses_creation_date` | August 2 + September 1 → `["2026-08": 2, "2026-09": 1]` |

Manual check: card values must equal `dashboard_stats()`; if the cards are right but a chart is
empty, the bug is in the JavaScript, not in the query.

## Boundaries

- Business logic (aggregation) stays in `selectors.py`; no ORM call in `views.py` or the template.
- Status transitions are untouched — the dashboard only reads `EC.status`.
- No new dependency; Chart.js is vendored like every other front-end asset.
- The page is read-only: no form, no POST, no endpoint that mutates data.

## Success Criteria

- [ ] This spec exists and has been approved (`SPEC_APPROVED`).
- [ ] `GET /dashboard/` → `200` for any authenticated user, `302` otherwise.
- [ ] 4 cards render and their numbers equal `dashboard_stats()`.
- [ ] 3 charts render; the donut shows every status, the bars match release occupancy,
      the line matches `ec_by_month`.
- [ ] All UI strings are in Portuguese.
- [ ] `uv run ruff check .` clean and `uv run pytest -q` green.

## Decisions (resolved 2026-10-06)

- **App:** `apps/backlog` (the EC and release data already belong to it; a new app would add
  ceremony without a dependency benefit).
- **Access:** every authenticated user (`LoginRequiredMixin`), not administrator-only — the page
  aggregates counts and contains no per-user private data.
- **Transport:** one `DashboardView` + `json_script`; no separate JSON endpoint in this iteration.
- **Chart library:** Chart.js v4 vendored under `static/vendor/chartjs/`.

## Open Questions

- Should `/dashboard/` become `LOGIN_REDIRECT_URL` (replacing `backlog:ec_list`)? Not part of
  this spec — decide separately.

## Branch Name

`feature/dashboard-charts`