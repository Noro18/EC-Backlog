# EC Backlog Management System — Architecture

## 1. Project summary

A Django web system for Timor Telecom (TT) that tracks EC (configuration specification) approvals. It replaces an Excel spreadsheet. It will run on a local server and be reached by IP address over the LAN, in a real production environment.

Workflow in one line: a Requester creates an EC, uploads the document, assigns a CD; the CD approves or rejects; the requester routes approved ECs to the DES team (closing them — the Release closes with its last EC) and resubmits rejected ones as a new document version; the requester records the go-live date on the closed Release.

## 2. Stack and tooling

- Python and dependencies are managed with **uv**. Never use `pip`, `python -m venv` or `requirements.txt`.
- Python version is pinned in `.python-version`. Do not change it without asking.
- This is an **application, not a library**: `[tool.uv] package = false` in `pyproject.toml`. Do not add `[build-system]`, `[project.scripts]` or a `src/` folder.
- Libraries in use: Django, django-auditlog, django-environ, django-filter, django-import-export, django-q2, django-tables2.
- Dev tools: ruff, pytest, pytest-django, factory-boy, pre-commit.
- Add libraries with `uv add <pkg>` (runtime) or `uv add --dev <pkg>` (dev only). Always commit `pyproject.toml` and `uv.lock` together.
- Run every command through `uv run`, for example `uv run python manage.py check`.
- Database: **SQLite, for both development and production** (decided 2026-09-29). The size of the team makes a single-file database proportionate and it removes a service to back up and monitor. The path still comes from `DATABASE_URL` via django-environ, so the engine stays swappable. Do not use engine-specific features (raw SQL, PostgreSQL-only fields) without asking.
- **Consequences of SQLite, accepted deliberately:**
  - Only one writer at a time. A write locks the whole database file, so a concurrent submission fails with `OperationalError: database is locked` after the timeout instead of waiting its turn. Handle or retry that path; never treat it as a validation error.
  - `select_for_update()` is **silently ignored** here — Django reports `has_select_for_update = False` and the `FOR UPDATE` clause is dropped without error. Do not rely on row-level locking anywhere in this codebase.
  - `journal_mode` is `delete` and the lock timeout is Django's 5s default. WAL mode and a longer `OPTIONS["timeout"]` are the known upgrades, deferred until lock errors are observed in production.
  - SQLite does not enforce `varchar` lengths, so `max_length` on `FileField` is a form-validation and portability guard, not a database constraint.
- The django-q2 worker runs as a **separate process with its own connection**, which is the most likely source of lock contention. Watch for task failures caused by `database is locked`.
- Deployment target: Docker Compose (web + django-q2 worker + database). Pin image versions. Never publish the database port in the production compose file.

## 3. Folder structure

```
ec-backlog/
├── manage.py
├── pyproject.toml
├── uv.lock
├── .python-version
├── config/                 # project package: settings, urls, asgi, wsgi. No business logic.
│   └── settings/           # base.py, local.py, production.py, test.py
├── apps/
│   ├── core/
│   ├── accounts/
│   ├── backlog/
│   ├── documents/
│   └── workflow/
├── templates/                # Contains all HTML files. Structure inside is separated by app/feature.
│   ├── base.html             # Main layout: navbar, role-based sidebar and content block.
│   ├── components/           # Reusable HTML partials.
│   │   ├── navbar.html
│   ├── accounts/             # Templates specific to the 'accounts' app.
│   │   ├── login.html
│   │   └── profile.html
│   ├── backlog/              # Templates specific to the 'backlog' app.
│   │   ├── ec_list.html
│   │   ├── ec_detail.html
│   │   ├── ec_form.html
│   │   └── release_list.html
│   ├── documents/            # Templates specific to the 'documents' app.
│   │   └── document_history.html
│   └── workflow/             # Templates specific to the 'workflow' app.
│       └── review_ec.html
├── static/                   # Static assets (CSS, JS, images).
│   ├── css/                  # Project stylesheets (app.css).
│   └── vendor/               # Third-party libraries (Bootstrap, Bootstrap Icons, HTMX).
├── docs/
└── .opencode/              # skills and specs (committed; node_modules is ignored)
```

Rules:

- All Django apps live under `apps/`. In each `apps.py` set `name = "apps.<app>"` and `label = "<app>"`.
- Settings are split into a package. Secrets come from environment variables (`.env`, never committed; `.env.example` is committed).
- Do not create apps named after pages or technical types (`homepage`, `forms`, `utils`).

## 4. Apps and responsibilities

| App | Owns | SRD |
|---|---|---|
| `accounts` | Custom `User`, roles (Requester, CD, DES Team, Administrator), permissions | RNF01 |
| `backlog` | `EC` and `Release` models, ID generation, Release capacity rule, list/search/filters, production go-live date, historical import | RF01–RF04, RF12, RNF04 |
| `documents` | Uploaded specification files, automatic versioning, version history | RF05, RF06 |
| `workflow` | Assigning a CD, approve/reject with comment, routing to DES, status transitions, email notifications | RF07–RF11, RNF03 |
| `core` | Shared abstract models (timestamps) and small helpers only | none |

Not separate apps:

- Audit log (RNF02): use `django-auditlog`. Register every model that matters.
- Notifications: `workflow/notifications.py`, sent through django-q2 (retry or failure alert, RNF03).
- Historical import (RNF04): `resources.py` in `backlog` plus a management command.

## 5. Dependency rule (must not be broken)

```
workflow → documents → backlog → accounts
```

An arrow means "may import from". Each app may import only from apps to its right. `core` may be imported by anyone and imports from no app.

- Never import upward. `backlog` must not import from `documents` or `workflow`; `documents` must not import from `workflow`; `accounts` imports from no other app.
- **Documented exception (EC_CREATE.md Decision 2, agreed 2026-10-05):** the single call site
  `NewECView.form_valid` in `backlog/views.py` may import `create_first_version` from
  `apps.documents.services`, because RF06 uploads the first document at EC creation time.
  No other `backlog` module may import from `documents` — in particular `backlog/forms.py`
  must not import `documents/validators.py`; file validation belongs in the `documents`
  service. Widening this exception requires a new entry here.
- **Documented exception (RF08_CD_NOTIFICATION.md Decision 1, agreed 2026-10-08):** the single call site
  `NewECView.form_valid` in `backlog/views.py` may import `queue_cd_assigned` from
  `apps.workflow.notifications`, because RF08 notifies the CD at EC creation time and the
  call is registered inside the creating transaction so a rollback discards it.
  No other `backlog` module may import from `workflow`.
- If you feel a need to import upward, stop. Either move the logic up into the higher app, or move the shared piece down. If neither fits, ask the user.
- Reference models in other apps by string (`"backlog.EC"`) in `ForeignKey` fields where it avoids an import.
- Reading data from below is fine (`ec.versions.all()` through reverse relations).

## 6. Code conventions

- **Thin views.** Views handle HTTP only. Business rules live in `services.py` (writes and state changes) and `selectors.py` (complex reads) inside the owning app.
- **Status changes go through `workflow` only.** `EC.status` is a field on `EC` (in `backlog`), but only `workflow` service functions change it, for example `approve_ec(ec, cd_user, comment)`. Never assign `ec.status` directly in a view, form, admin action or import.
- **Wrap multi-step writes** in `transaction.atomic()`.
- Follow ruff (`uv run ruff check .` and `uv run ruff format .`). Line length 100.
- Use `select_related` / `prefetch_related` for list pages (backlog view, tables).
- Set `TIME_ZONE` to the local timezone. Store timestamps as timezone-aware.

## 7. Domain rules (from the SRD and confirmed business rules)

- **EC ID:** unique, sequential, generated automatically. Historical IDs (2019–2026) are imported and **must be preserved**. Design generation so new IDs never collide with imported ones.
- **Release ID format:** `TT_ON_AAAA-NNN` (for example `TT_ON_2026-001`). One Release has many ECs.
- **Release capacity:** confirmed with the team — a Release is open while not all its ECs are closed, and it accepts at most **10 ECs**. When it reaches 10 it closes to new ECs, even if not all are approved or closed yet. If no Release is open, create a new one and assign the EC to it.
- **Concurrency:** assigning an EC to a Release must not allow an 11th EC when two users submit at once. The capacity check runs inside `transaction.atomic()` and the rule is enforced by SQLite's exclusive write lock, **not** by `select_for_update()` — that call is a silent no-op on this engine (see section 2). Consequence: if the project ever moves to PostgreSQL, an 11th EC becomes possible and the guard must be reinstated, because nothing in the code will catch it. Test the capacity rule sequentially; do not claim a passing concurrent-write test as proof, since it passes for the wrong reason on SQLite.
- **Statuses:** In Validation, Approved, Rejected, Sent to DES, Closed, Cancelled. Transitions are automatic, driven by `workflow`: validation → Approved/Rejected; rejection → back to Validation on resubmit; routing an approved EC closes it; a Release closes automatically once all its ECs are closed.
- **Rejection:** the CD must record a comment. The requester corrects and uploads a new document version. The EC ID stays the same and the version increments automatically (v1.0, v1.1, v2.0). All previous versions are kept.
- **Notifications:** email the CD on assignment (RF08) and notify the requester of the decision (RF10). Sending must be reliable, with retry or an alert on failure (RNF03).
- **Audit (RNF02):** every creation, assignment, approval, rejection and routing is recorded with user and date/time, immutably.
- **Import (RNF04):** the history comes from an Excel file. Use django-import-export with dry-run preview. The Excel format needs `django-import-export[xlsx]`.
- **Roles:** Requester, CD, DES Team, Administrator. Enforce permissions in views and services, not only in templates.

## 8. Database and migrations

- `AUTH_USER_MODEL = "accounts.User"` is **permanent**. The table name, the primary key and the `username` / `password` / `role` columns are referenced by `admin`, `auth` and `auditlog`, so they are never renamed, retyped or removed.
- Additive changes to `accounts.User` (new fields, new role values, new constraints) are allowed in a normal migration, as they were pre-release on 2026-09-29 when `name` was added and `email` was made unique. Ship them in a **new** migration, never by editing `0001_initial`.
- Renaming or dropping an existing `accounts.User` column, or changing `AUTH_USER_MODEL`, requires explicit user approval and a written data migration first.
- Never edit a migration that has been applied or committed, unless fixing a circular dependency.
- After changing any model, follow `.opencode/skills/django-db-integrity/SKILL.md`.
- Before any production migration: take a database backup first. On SQLite, copy the database with `sqlite3 db.sqlite3 ".backup backups/backup.db"` or stop the app first — `cp` during an active write produces a torn file.
- Never run destructive commands (`flush`, `reset_db`, dropping tables, `docker compose down -v`) without explicit user approval. `db.sqlite3` is the entire production dataset; losing it loses every EC, document and audit record, so treat it as irreplaceable.

## 9. Testing

- Follow `.opencode/skills/django-tdd-loop/SKILL.md`: failing test first, then the minimum code, then refactor.
- Tests live in `apps/<app>/tests/` (`test_models.py`, `test_services.py`, `test_views.py`) with test data in `factories.py` using factory-boy.
- Required tests: Release capacity, version increment on resubmission, status transitions and who may perform them, notification sending and failure handling, CSV/Excel import dry-run. Capacity is tested **sequentially** (the 11th EC is refused); a true concurrent-write test cannot be written on SQLite, because SQLite's whole-file write lock makes it pass regardless of the code under test. See section 2.
- Run `uv run pytest` (or `uv run python manage.py test <app>`) and `uv run ruff check .` before declaring work finished.

## 10. Workflow with the user

- New features need a spec first: follow `.opencode/skills/spec-driven-development/SKILL.md` (write `.opencode/specs/FEATURE_NAME.md`, wait for the user to reply `SPEC_APPROVED` before writing code).
- Keep changes small and focused. Do not refactor unrelated code.
- Do not add dependencies, apps or top-level folders without asking.
- Never commit `.env`, database files, backups (`backups/`, `*.dump`) or uploaded documents.
- Do not invent requirements. If the SRD is silent or ambiguous, ask.

## 11. Security and production checklist

- `DEBUG = False`, a long random `SECRET_KEY`, and `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` set to the server address in production.
- Run `uv run python manage.py check --deploy` and address every warning, or record why it is accepted.
- Uploaded documents are validated (type and size) and stored outside the code tree on a persistent volume.
- Uploaded files are served under `/media/` by the web server in production (nginx: `location /media/ { alias <MEDIA_ROOT>/; }`); Django only registers this route when `DEBUG = True` (`django.conf.urls.static.static` in `config/urls.py`).
- Backups are stored on a different machine, and a restore has been tested at least once. On SQLite this is the whole production database in one file: back it up with the `.backup` command, never `cp` while the server is writing.