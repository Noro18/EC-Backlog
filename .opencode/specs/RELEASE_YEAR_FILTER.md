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
- **Year Mismatch (Historical & Cross-Year Releases)**: ECs submitted in one year may belong to a release of another year (especially in historical imports 2019–2026). The detail view should primarily show ECs linked via `release.ecs`, while allowing clear visibility of their respective years.
- **Empty Filter Results**: If a user filters releases by a year with no releases, render the existing `empty_text` ("Nenhuma Release encontrada.").

## 5. Acceptance Criteria
1. The Release list page features a year filter input/dropdown that successfully filters the table by the selected calendar year.
2. The Release detail page correctly lists all ECs belonging to that release.
3. All existing tests pass (`uv run pytest`), and new tests cover the year filtering functionality.
