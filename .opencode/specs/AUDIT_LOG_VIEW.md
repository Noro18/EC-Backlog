# Spec — Full Audit Log View (`Registo de Auditoria`)

## Objective

Replace the external Django admin link (`admin:auditlog_logentry_changelist`) behind `Ver todos os logs` on the administrator dashboard with a native, polished, Portuguese-localized full audit log page at `/backlog/audit-log/`.

- As an administrator, I visit `/backlog/audit-log/` and view all historical system activity logs in reverse chronological order, formatted as readable PT sentences (matching the dashboard feed style).
- As an administrator, I can paginate through the audit logs (e.g., 25 or 50 per page via `django-tables2`).
- As a non-administrator user (Requester, CD, DES Team), attempting to access `/backlog/audit-log/` is forbidden (403 Forbidden).
- The "Ver todos os logs" button on the administrator dashboard links to this new native page instead of the Django admin backend.

## Tech Stack

Django 6.1, django-tables2 (`ActivityTable` / `FullAuditLogTable`), django-auditlog (`LogEntry`), factory-boy. **No new dependency.**

## Commands

```bash
uv run pytest apps/backlog/tests/test_audit_log_view.py   # feature tests
uv run pytest                                             # full suite
uv run ruff check .                                       # lint
uv run python manage.py runserver                         # manual check
```

## System Architecture

```
apps/backlog/
├── selectors.py   # EDIT: expand audit log helpers or add `full_audit_log_entries()` queryset/list builder
├── tables.py      # EDIT / NEW: pagination-ready table for full audit log
├── views.py       # NEW: AuditLogListView (LoginRequiredMixin, UserPassesTestMixin, SingleTableView)
├── urls.py        # EDIT: path("audit-log/", AuditLogListView.as_view(), name="audit_log")
└── tests/
    └── test_audit_log_view.py  # NEW: permission tests, list rendering, pagination, PT sentence check

templates/backlog/
├── audit_log.html       # NEW: dedicated table page with breadcrumb / back to dashboard button
└── dashboard.html       # EDIT: update `Ver todos os logs` href to `{% url 'backlog:audit_log' %}`
```

Import direction stays legal: `backlog` reads `auditlog.models.LogEntry` and `apps.accounts.models.User` (`backlog → accounts`, §5).

## Database Schema Changes

**None.** No migration, no model edits. Reads from `auditlog_logentry`.

## Input / Output

**Input:** HTTP GET `/backlog/audit-log/`, session role `administrator`.

**Access Rules:**
- `is_authenticated=False` → redirect to `LOGIN_URL` (302).
- `is_authenticated=True` and `role != "administrator"` → HTTP 403 Forbidden.
- `role == "administrator"` → HTTP 200, renders `audit_log.html` with paginated table of all audit logs.

**Output (Context & Table):**
- Table pagination: default 25 rows per page.
- Columns: `Data/Hora` (timestamp) and `Ação` (Portuguese sentence, e.g., "João Soares aprovou o EC 2026-005").

## Acceptance Criteria

1. Administrator can navigate from dashboard via `Ver todos os logs` to `/backlog/audit-log/`.
2. Non-administrator trying to access `/backlog/audit-log/` gets 403.
3. Pagination works correctly when log count exceeds page size.
4. All unit tests pass and `ruff check .` is clean.
