# Spec: Gestão de Utilizadores — read-only (accounts)

## Objective

Build the first working page under the administrator sidebar: a read-only list of users at
`/accounts/users/`. Today `base.html:64` renders "Gestão de Utilizadores" as `href="#"`, so the
menu is dead.

- As an administrator, I open `/accounts/users/` and see a table of every user.
- As an administrator, I sort by username or role and paginate the list.
- As an administrator, I read each user's name, username, email, role and active state.
- As a non-administrator, I am refused.

**Out of scope:** creating, editing or deleting users; changing roles; resetting passwords; any
write operation. This is scope **A (read-only)** as agreed on 2026-10-02. Scope B (role editing)
and C (full CRUD) are separate specs.

## Tech Stack

Django 6.1, django-tables2 (already used by `apps/backlog/tables.py`), factory-boy.
No new dependency.

## Commands

```bash
uv run pytest apps/accounts/tests/test_views.py   # feature tests
uv run pytest                                     # full suite
uv run ruff check . && uv run ruff format .       # lint
uv run python manage.py runserver                 # manual check at /accounts/users/
```

## System Architecture

Follows the pattern already proven by `apps/backlog/`:

```
apps/accounts/
├── tables.py           # NEW: UserTable (django-tables2)
├── selectors.py        # NEW: list_users() — first real selector in the project
├── urls.py             # NEW: app_name="accounts", one path
├── views.py            # REPLACE placeholder with UserListView
└── tests/
    └── test_views.py   # NEW: first view test in the project

templates/accounts/
└── user_list.html      # NEW

config/urls.py          # add include("apps.accounts.urls")
```

Import direction: `accounts` imports from nothing (§5). `tables.py` imports only `django_tables2`
and `.models`. No upward imports anywhere.

## Database Schema Changes

**None.** `accounts.User` already has `username`, `email`, `role`, `is_active`, `date_joined`,
`last_login`, `name`. `full_name` is an existing property.

No migration. No model edits.

## Input / Output

**Input:** HTTP GET on `/accounts/users/`. Optional query params handled by django-tables2:
`?sort=username`, `?page=2`.

**Output:**

| Case | Status | Result |
|---|---|---|
| Administrator, valid | 200 | Table of users, `table` in context |
| Non-administrator (any role) | 403 | Forbidden — must not see the page |
| Anonymous | 302 | → `admin:login` (Django default `LOGIN_URL`) |
| Empty table | 200 | Portuguese empty message |
| Sort by `username` | 200 | Rows ordered A→Z |
| `?page=2` with >25 users | 200 | Second page reachable |

**Columns:** Nome, Utilizador, Email, Role, Estado, última atividade (`last_login`), Ações.

`Ações` is **not** a link to an edit page — no edit page exists in scope A. It renders as a disabled
button marked for scope B, so the menu item is visibly wired but not misleading. This is a deliberate
decision, see Open Questions.

**Role badges** reuse the soft palette already in `static/css/app.css`. Mapping:

| Role | Badge class |
|---|---|
| `requester` | `bg-info` |
| `cd` | `bg-warning` |
| `des_team` | `bg-success` |
| `administrator` | `bg-danger` |

## Edge Cases

1. **Two administrators exist** (`admin`, `ana`). Read-only means neither can lock the other out in
   this scope. Recorded here because scope C must add a self-deletion guard.
2. **`full_name` can be empty.** `User.full_name` returns `name` or falls back to
   `first_name last_name`, but both can be blank — `UserFactory` sets `first_name`, yet real rows may
   not. The column must fall back to the username rather than rendering blank.
3. **`last_login` is `null`** for users who have never logged in. Must render a Portuguese
   placeholder, not `None` or an empty cell that looks like a bug.
4. **N+1 queries.** The table must resolve with a bounded query count, asserted with
   `django.test.AssertNumQueries`.
5. **Anonymous access.** `LOGIN_URL` is not set in settings, so Django falls back to
   `admin:login`. Acceptable for now; a dedicated login page is a separate spec
   (`.opencode/specs/ACCOUNTS_LOGIN.md`).
6. **Permission check lives in the view, not the template.** `ARCHITECTURE.md` §7 requires
   enforcement in views and services. Hiding a sidebar link is not access control.
7. **Pre-existing bug, not fixed here.** `base.html:46` compares `user.role == 'CD'` (capital)
   against the stored value `'cd'`. Unrelated to this page; belongs to the role-sidebar fix.

## Project Structure

See System Architecture above.

## Code Style

Thin views (§6). django-tables2 `SingleTableView` handles the table; the selector holds the query.

```python
# selectors.py
def list_users():
    return User.objects.all().order_by("username")
```

```python
# views.py
class UserListView(SingleTableView, LoginRequiredMixin, UserPassesTestMixin):
    ...
```

Line length 100, ruff-formatted. Match the existing `apps/backlog/tables.py` style
(`TemplateColumn` for badges, `template_name = "django_tables2/bootstrap5.html"`, `per_page = 25`).

## Testing Strategy

TDD: failing test first. This will be the **first view test in the project** — the existing 392 test
lines live entirely in `test_models.py` files and never perform an HTTP request, so no view has ever
been exercised. `UserFactory` lives in `apps/backlog/tests/factories.py` (odd location, pre-existing;
not moved in this scope).

Scope agreed on 2026-10-02: the set is **capped at 6 tests, all about what the page renders**, not
about backend behaviour. Six are enough for a read-only table and none of them tests a framework
default that django-tables2 already guarantees.

| # | Test | Frontend concern it protects |
|---|---|---|
| 1 | Administrator GETs `/accounts/users/` → 200 | the page opens at all |
| 2 | All six real usernames appear in the HTML | the table actually pulled the rows |
| 3 | Empty `full_name` falls back to the username | no blank name cell |
| 4 | `last_login` is `null` → Portuguese placeholder, not `None` | never-logged-in users render cleanly |
| 5 | Each role maps to its badge class | the four role colours are correct |
| 6 | 30 users → `?page=2` returns 200 with a different user | the pagination control works |

Deliberately excluded, and why:

- **403 for non-administrators, 302 for anonymous.** Permission enforcement still ships in the view
  (`ARCHITECTURE.md` §7 requires it) — it is simply not covered by a test in this scope. Carried as a
  known gap, not silently dropped.
- **`AssertNumQueries`.** Performance, not presentation. The table has no reverse relations, so N+1
  is not a realistic risk on this page.
- **Ascending/descending sort, `table` in context, empty-table message.** These assert
  django-tables2 internals. They pass or fail with the library version, not with our code.

If a test in the excluded list later becomes genuinely risky to skip, it gets added then — the cap
is not a quota to fill later.

## Boundaries

- **Always:** TDD (red → green → refactor), `uv run pytest` + ruff before done, thin views,
  permission enforced in the view layer.
- **Ask first:** new dependencies, any change to `accounts.User` or a migration, adding create/edit/
  delete actions, any `@login_required` added to pre-existing views, touching the `base.html` role bug.
- **Never:** implement scope B or C "while we're here", write operations in this spec, change
  `AUTH_USER_MODEL`, modify `backlog` files except the URL link, commit `.env` or `db.sqlite3`.

## Success Criteria

- `/accounts/users/` returns 200 for an administrator and lists all six real users.
- Role badges, the `full_name` fallback, the `last_login` placeholder and pagination all work.
- 6 new tests pass; full suite green (50); ruff clean.
- Zero migrations, zero changes to `accounts.User`, zero write operations.

## Open Questions

1. **What should the `Ações` column show?** Options: disabled "Editar" button (honest but ugly),
   omit the column entirely (cleanest for read-only), or a disabled button with a tooltip saying it
   arrives in scope B. **Recommend omitting it for now** — a dead button in a read-only table is
   noise.
2. **Should the sidebar link be wired in this spec?** `base.html:64` currently points at `#`.
   Changing that one line makes the menu work. Recommend yes — it is part of "the page exists and is
   reachable", and it is the only `base.html` line touched.

## Branch Name

`feature/accounts-user-list`