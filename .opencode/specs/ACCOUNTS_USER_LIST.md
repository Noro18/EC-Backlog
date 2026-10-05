# Spec: Gestão de Utilizadores — read-only (accounts)

## Objective

Build the first working page under the administrator sidebar: a read-only list of users at
`/users/`. Today `base.html:63` renders "Gestão de Utilizadores" as `href="#"`, so the
menu is dead.

> URL note (updated 2026-10-05): `config/urls.py` already mounts `apps.accounts.urls` at the root
> (`path("", include("apps.accounts.urls"))`, shipped in PR #20), so the route is `/users/`, **not**
> `/accounts/users/`. Nothing to add to `config/urls.py`.

- As an administrator, I open `/users/` and see a table of every user.
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
uv run ruff check .                               # lint
uv run python manage.py runserver                 # manual check at /users/
```

> `uv run ruff format .` is **not** part of the done-check right now: 5 pre-existing files are
> already unformatted, so it fails regardless of this work. Run `ruff check .` instead.

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

config/urls.py          # ALREADY INCLUDES accounts urls at root — no change
```

Import direction: `accounts` imports from nothing (§5). `tables.py` imports only `django_tables2`
and `.models`. No upward imports anywhere.

## Database Schema Changes

**None.** `accounts.User` already has `username`, `email`, `role`, `is_active`, `date_joined`,
`last_login`, `name`. `full_name` is an existing property.

No migration. No model edits.

## Input / Output

**Input:** HTTP GET on `/users/`. Optional query params handled by django-tables2:
`?sort=username`, `?page=2`.

**Output:**

| Case | Status | Result |
|---|---|---|
| Administrator, valid | 200 | Table of users, `table` in context |
| Non-administrator (any role) | 403 | Forbidden — must not see the page |
| Anonymous | 302 | → `/` (`accounts:login` — `LOGIN_URL` is set in `config/settings/base.py:156`) |
| Empty table | 200 | Portuguese empty message |
| Sort by `username` | 200 | Rows ordered A→Z |
| `?page=2` with >25 users | 200 | Second page reachable |

**Columns:** Nome, Utilizador, Email, Role, Estado, última atividade (`last_login`).

`Ações` is **omitted** (decided 2026-10-05, see Decisions below): with no edit page in scope A, any
button would be dead. The column can be added later when scope B ships.

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
5. **Anonymous access.** `LOGIN_URL = "accounts:login"` **is** set (`config/settings/base.py:156`),
   so an anonymous request is redirected to `/`, which renders `accounts/login.html` (see
   `.opencode/specs/ACCOUNTS_LOGIN.md`). The spec's original assumption — no `LOGIN_URL`, Django
   falling back to `admin:login` — is obsolete.
6. **Permission check lives in the view, not the template.** `ARCHITECTURE.md` §7 requires
   enforcement in views and services. Hiding a sidebar link is not access control.
7. **`base.html` role bug — FIXED.** `user.role == 'CD'` was corrected to `'cd'` (and the CD sidebar
   links wired) in PR #24, merged 2026-10-05. Kept here only as history; nothing to do in this spec.

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

TDD: failing test first.

> Updated 2026-10-05: this is **no longer the first view test in the project** — `apps/backlog/`
> gained `test_views.py` in PR #19/#23. Accounts simply gets its own `tests/test_views.py` next to
> the existing `tests/test_models.py`, mirroring that pattern.
>
> **Open decision:** `UserFactory` currently lives in `apps/backlog/tests/factories.py`. Importing it
> from `apps/accounts` tests would be an *upward* import (`accounts` is the bottom layer, §5).
> Options: (A) create a tiny `apps/accounts/tests/factories.py`, or (B) import from `backlog`
> anyway since it is test-only. Not yet decided.

Scope agreed on 2026-10-02: the set is **capped at 6 tests, all about what the page renders**, not
about backend behaviour. Six are enough for a read-only table and none of them tests a framework
default that django-tables2 already guarantees.

| # | Test | Frontend concern it protects |
|---|---|---|
| 1 | Administrator GETs `/users/` → 200 | the page opens at all |
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

- `/users/` returns 200 for an administrator and lists all six real users.
- Role badges, the `full_name` fallback, the `last_login` placeholder and pagination all work.
- 6 new tests pass; full suite green (69 = 63 existing + 6 new, as of 2026-10-05); ruff clean.
- Zero migrations, zero changes to `accounts.User`, zero write operations.

## Decisions (resolved 2026-10-05)

1. **`Ações` column: omit it.** A dead button in a read-only table is noise. Revisit when scope B
   (role editing) gets its own spec.
2. **Sidebar link: yes, wire it** — `base.html:63` goes from `href="#"` to
   `{% url 'accounts:user_list' %}`. It is the only `base.html` line touched. The implementer does
   this as the final step of the same branch.

## Open Questions

None. The two questions above were the last ones outstanding.

## Branch Name

`feature/accounts-user-list`