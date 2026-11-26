# Specification: Release Year Filtering and EC Alignment (Issue #104)

## 1. Overview
This specification covers the implementation of year-based filtering on the Release list page and ensuring ECs displayed on the Release detail page align with release context and year.

## 2. Affected Components
- **`apps/backlog/selectors.py`**:
  - Update release querysets (`release_with_ec_count`) to accept an optional `year` parameter for filtering.
- **`apps/backlog/views.py`**:
  - `ReleaseListView`: Read `?year=` from `request.GET` and pass it to the release selector.
  - `ReleaseDetailView`: Ensure associated ECs shown in `ec_table` are correctly scoped and filtered.
- **`templates/backlog/release_list.html`**:
  - Add a year filter form (dropdown/input for year + submit/clear buttons) following the established EC list toolbar pattern.
- **`templates/backlog/release_detail.html`**:
  - Ensure clear visibility of release year and associated ECs.

## 3. Database Schema Changes
- **None**. Both `Release` (`year`) and `EC` (`year`, `release`) models already have the required fields. No database migrations are required.

## 4. Edge Cases & Handling
- **Default Year**: When the page is opened without any `?year=` parameter, the filter defaults to the **current calendar year** (`timezone.localdate().year`). An explicit `?year=` — including the empty value emitted by the "Todos os anos" option — always overrides the default and lists every year.
- **Year Mismatch (Historical & Cross-Year Releases)**: ECs submitted in one year may belong to a release of another year (especially in historical imports 2019–2026). The detail view should primarily show ECs linked via `release.ecs`, while allowing clear visibility of their respective years.
- **Invalid Year**: A non-numeric `?year=abc` must not crash the view (HTTP 200); the selector ignores the unparsable value.
- **Empty Filter Results**: If a user filters releases by a year with no releases, render the existing `empty_text` ("Nenhuma Release encontrada."). The current year is always offered in the dropdown even when no release exists for it yet.

## 5. Acceptance Criteria
1. The Release list page features a year filter input/dropdown that successfully filters the table by the selected calendar year.
2. Opening the Release list with no `?year=` parameter shows the current calendar year by default (table and dropdown selection).
3. The "Todos os anos" option (`?year=`) clears the default and shows releases from every year.
4. The Release detail page correctly lists all ECs belonging to that release.
5. All existing tests pass (`uv run pytest`), and new tests cover the year filtering functionality.
