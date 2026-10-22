# Spec: Gestão de Utilizadores (accounts) — scope A + list actions

> **Amended 2026-10-22.** Scope A was read-only and explicitly omitted every action column. This
> amendment adds three *navigation* actions — `?q=` search, an `Editar` row link and a
> `Novo Utilizador` button — all pointing at the existing Django admin, so the page still performs
> **no write of its own**. In-app create/edit/delete forms remain out of scope (issue #68). Where a
> decision from 2026-10-05 still holds it is kept; where it does not, it is reversed in the
> *Decisions (resolved 2026-10-22)* section below.

## Objective

Build the first working page under the administrator sidebar: a list of users at
`/users/`. Today `base.html:63` renders "Gestão de Utilizadores" as `href="#"`, so the
menu is dead.

> URL note (updated 2026-10-05): `config/urls.py` already mounts `apps.accounts.urls` at the root
> (`path("", include("apps.accounts.urls"))`, shipped in PR #20), so the route is `/users/`, **not**
> `/accounts/users/`. Nothing to add to `config/urls.py`.

- As an administrator, I open `/users/` and see a table of every user.
- As an administrator, I sort by username or role and paginate the list.
- As an administrator, I read each user's name, username, email, role and active state.
- As an administrator, I filter the list with `?q=`, matching name, username or email.
- As an administrator, I open a user's edit form in the Django admin via the row's `Editar` link.
- As an administrator, I open the Django admin add form via `Novo Utilizador`.
- As a non-administrator, I am refused.

**Out of scope:** creating, editing or deleting users *through the app*; changing roles; resetting
passwords; any write operation executed by `apps/accounts`. This remains scope **A (read-only)** as
agreed on 2026-10-02, plus the navigation actions amended on 2026-10-22. Scope B (in-app role
editing) and C (full CRUD) stay separate specs — now tracked by issue #68.

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
├── admin.py            # EDIT 2026-10-22: auditlog.register(User) — feeds the admin dashboard (RNF02)
├── tables.py           # EDIT: UserTable + `edit` column (added 2026-10-22)
├── selectors.py        # EDIT: list_users(q=None) — `q` added 2026-10-22
├── urls.py             # NEW: app_name="accounts", one path — unchanged since scope A
├── views.py            # EDIT: UserListView.get_queryset forwards request.GET["q"]
└── tests/
    ├── test_admin.py   # EDIT 2026-10-22: one test that admin writes reach the audit log
    └── test_views.py   # EDIT: +2 tests (search, Editar link), +1 (403)

templates/accounts/
└── user_list.html      # EDIT 2026-10-22: search form + Novo Utilizador in the page header

config/urls.py          # ALREADY INCLUDES accounts urls at root — no change
```

Import direction: `accounts` imports from nothing (§5). `tables.py` imports `django_tables2`,
`django.urls.reverse` and `.models`. No upward imports anywhere in production code.

## Database Schema Changes

**None.** `accounts.User` already has `username`, `email`, `role`, `is_active`, `date_joined`,
`last_login`, `name`. `full_name` is an existing property.

No migration. No model edits.

## Input / Output

**Input:** HTTP GET on `/users/`. Optional query params:

| Param | Owner | Effect |
|---|---|---|
| `?sort=username` | django-tables2 | rows ordered A→Z |
| `?page=2` | django-tables2 | second page |
| `?q=<text>` | `list_users(q)` (added 2026-10-22) | `Q(name) \| Q(username) \| Q(email)`, `icontains`, case-insensitive |

**Output:**

| Case | Status | Result |
|---|---|---|
| Administrator, valid | 200 | Table of users, `table` in context |
| Non-administrator (any role) | 403 | Forbidden — must not see the page |
| Anonymous | 302 | → `/` (`accounts:login` — `LOGIN_URL` is set in `config/settings/base.py:156`) |
| Empty table | 200 | Portuguese empty message |
| `?q=` matches nothing | 200 | Portuguese empty message, not an error |
| Sort by `username` | 200 | Rows ordered A→Z |
| `?page=2` with >25 users | 200 | Second page reachable |

**Columns:** Nome, Utilizador, Email, Role, Estado, última atividade (`last_login`), **Ações**
(one `Editar` link — added 2026-10-22).

**Page header (added 2026-10-22):** a `Pesquisar nome...` search box (`role="search"`, GET form,
round-trips the current `?q=`) and a `Novo Utilizador` button.

**`Ações` — reversed 2026-10-22.** Scope A omitted it because "with no edit page in scope A, any
button would be dead". There is still no *in-app* edit page, but the column now carries an `Editar`
link to the existing Django admin change form
(`/admin/accounts/user/<pk>/change/`), and `Novo Utilizador` points at
`/admin/accounts/user/add/`. Both are navigation to a form that already exists
(`apps/accounts/admin.py::CustomUserAdmin`), so the page still writes nothing itself.
See *Decisions (resolved 2026-10-22)*.

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
def list_users(q=None):          # q added 2026-10-22
    users = User.objects.all().order_by("username")
    if q:
        users = users.filter(Q(name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q))
    return users
```

```python
# views.py
class UserListView(SingleTableView, LoginRequiredMixin, UserPassesTestMixin):
    def get_queryset(self):
        return list_users(self.request.GET.get("q"))
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

> **Amended 2026-10-22:** the cap becomes **9 tests in `test_views.py` plus 1 in `test_admin.py`**.
> The page gained a query param, a link column and a header button — none of them guaranteed by
> django-tables2 — and `auditlog.register(User)` in `admin.py` had no coverage at all, which matters
> because the administrator dashboard's `Ações hoje` / `Atividade recente` widgets read that log.

| # | Test | Frontend / contract concern it protects |
|---|---|---|
| 1 | Administrator GETs `/users/` → 200 | the page opens at all |
| 2 | All six real usernames appear in the HTML | the table actually pulled the rows |
| 3 | Empty `full_name` falls back to the username | no blank name cell |
| 4 | `last_login` is `null` → Portuguese placeholder, not `None` | never-logged-in users render cleanly |
| 5 | Each role maps to its badge class | the four role colours are correct |
| 6 | 30 users → `?page=2` returns 200 with a different user | the pagination control works |
| 7 | `?q=` matches `maria.costax`, drops `joao.soares` | `list_users(q)` filters name/username/email |
| 8 | `Editar` href equals `/admin/accounts/user/<pk>/change/` | the row link never points at a dead route |
| 9 | Non-administrator gets **403** on `/users/` | closes the gap carried since scope A |
| 10 | A user created through the admin writes a `LogEntry` | RNF02 — feeds `Ações hoje` on the dashboard |

Deliberately excluded, and why:

- **403 for non-administrators — CLOSED 2026-10-22** (test 9). It was an acceptable known gap while
  the page was purely read-only; now that the rows carry links into the admin, a refused request is
  worth proving rather than assuming.
- **`AssertNumQueries`.** Performance, not presentation. The table has no reverse relations, so N+1
  is not a realistic risk on this page.
- **Ascending/descending sort, `table` in context, empty-table message.** These assert
  django-tables2 internals. They pass or fail with the library version, not with our code.

If a test in the excluded list later becomes genuinely risky to skip, it gets added then — the cap
is not a quota to fill later.

## Boundaries

- **Always:** TDD (red → green → refactor), `uv run pytest` + ruff before done, thin views,
  permission enforced in the view layer.
- **Ask first:** new dependencies, any change to `accounts.User` or a migration, adding **in-app**
  create/edit/delete actions, any `@login_required` added to pre-existing views, touching the
  `base.html` role bug.
  *Amended 2026-10-22:* links **to** the Django admin are in scope here (they are navigation, not a
  write performed by `apps/accounts`); building our own forms is not.
- **Never:** implement scope B or C "while we're here", write operations performed by this app,
  change `AUTH_USER_MODEL`, modify `backlog` files except the URL link, commit `.env` or `db.sqlite3`.

## Success Criteria

- `/users/` returns 200 for an administrator and lists all six real users.
- Role badges, the `full_name` fallback, the `last_login` placeholder and pagination all work.
- `?q=` filters by name, username or email; a non-match shows the Portuguese empty message.
- Every row's `Editar` and the header's `Novo Utilizador` resolve to a working Django admin URL.
- 10 tests pass (6 original + 3 added here + 1 in `test_admin.py`); full suite green; ruff clean.
- Zero migrations, zero changes to `accounts.User`, zero write operations performed by the app.

## Decisions (resolved 2026-10-05)

1. **`Ações` column: omit it.** A dead button in a read-only table is noise. Revisit when scope B
   (role editing) gets its own spec. — *Superseded 2026-10-22, see the next section.*
2. **Sidebar link: yes, wire it** — `base.html:63` goes from `href="#"` to
   `{% url 'accounts:user_list' %}`. It is the only `base.html` line touched. The implementer does
   this as the final step of the same branch.

## Decisions (resolved 2026-10-22)

1. **Search lives in the selector, not the table.** `list_users(q=None)` takes the raw `q` and applies
   `icontains` on `name`, `username` and `email`; `UserListView.get_queryset` only forwards
   `request.GET.get("q")`. Keeps django-tables2 out of query building (§5, thin views).
2. **`Ações` / `Editar`: reversed — ship it as a link.** The column was omitted for being dead; it now
   points at `admin:accounts_user_change`, a URL that exists today. Django-tables2 column
   `orderable=False`.
3. **`Novo Utilizador`: ship it as a link**, not a form, pointing at `admin:accounts_user_add`.
4. **`auditlog.register(User)` belongs in `apps/accounts/admin.py`,** next to `CustomUserAdmin`, so
   user creations/edits reach the audit feed (RNF02) that the administrator dashboard reads.
5. **The dashboard does not host the user table.** The list, its search and its buttons live only on
   `/users/`; `Painel do Administrador` keeps KPI cards and the activity feed (spec
   `ADMIN_DASHBOARD.md`).

## Open Questions

- **`UserFactory` import direction (carried over, still undecided).** `apps/accounts/tests/*.py`
  import `UserFactory` from `apps.backlog.tests.factories`. That is an *upward* import (`accounts` is
  the bottom layer, §5). Options: (A) a tiny `apps/accounts/tests/factories.py`, or (B) accept it as
  test-only. Not resolved here — needs a decision from the user before it is called settled.

## Branch Name

- Original scope A: `feature/accounts-user-list` (PR #36 area, merged 2026-10-05)
- Scope A + list actions: `feat/user-list-actions` (PR #70)