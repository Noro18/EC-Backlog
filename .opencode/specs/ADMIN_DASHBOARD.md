# Spec — Administrator Dashboard (`Painel do Administrador`)

## Objective

Replace the `Widgets específicos do Administrador — em construção` placeholder on
`/backlog/dashboard/` with a real panel for the `administrator` role.

- As an administrator, I see four KPI cards: Utilizadores (total/active), Releases (total/open),
  Total de EC (pending review) and Ações hoje.
- As an administrator, I read the five latest system actions as one Portuguese sentence each, with
  the time on the left.
- As an administrator, I jump to the full audit trail through `Ver todos os logs`.

> **Scope split (2026-10-22).** `.opencode/specs/DASHBOARD.md` covers the shared overview for
> Requester, CD and DES Team — it never mentions the administrator and its own *Decisions* say the
> page is "every authenticated user… not administrator-only". This spec owns the `administrator`
> branch of the same view. The two specs share one template but nothing else.

## Tech Stack

Django 6.1, django-tables2 (`ActivityTable`), django-auditlog (`LogEntry` — already a dependency,
already registering `EC`, `Release`, `Review`, `DocumentVersion`), factory-boy.
**No new dependency.**

## Commands

```bash
uv run pytest apps/backlog/tests/test_dashboard.py   # feature tests
uv run pytest                                        # full suite
uv run ruff check .                                  # lint
uv run python manage.py runserver                    # manual check as an administrator
```

> `uv run ruff format .` is **not** part of the done-check: pre-existing files are unformatted, so
> it fails regardless of this work. Run `ruff check .` (same note as `ACCOUNTS_USER_LIST.md`).

## System Architecture

```
apps/backlog/
├── selectors.py   # NEW: admin_dashboard(user) + _log_activity() — all queries and all wording
├── tables.py      # NEW: ActivityTable (django-tables2, {time, description} dicts)
├── views.py       # EDIT: `elif role == "administrator"` inside DashboardView.get_context_data
└── tests/
    └── test_dashboard.py   # EDIT: TestAdminDashboard (7 tests) replaces the admin placeholder test

templates/backlog/dashboard.html
                    # EDIT: header + 4 KPI cards + Atividade recente card; `{% elif %}` branch
static/css/app.css  # NEW: .kpi-icon, .kpi-violet
```

Import direction stays legal: `backlog` reads `auditlog.models.LogEntry` and `apps.accounts.models.User`
(`backlog → accounts`, §5). The view only wires selector output into tables — no ORM call, no
formatting (§6).

**Cross-branch note:** `auditlog.register(User)` lives on `feat/user-list-actions` (PR #70,
`apps/accounts/admin.py`), not here. Until that merges, the feed shows EC / Release / Review /
DocumentVersion rows; user rows appear afterwards. Nothing in this spec depends on them.

## Database Schema Changes

**None.** No migration, no model edits, no change to `EC.status` or any field.
The feed is a read of the existing `auditlog_logentry` table.

## Input / Output

**Input:** HTTP GET `/backlog/dashboard/`, session role `administrator`.
No query params of its own (the admin panel ignores `?q=`; user search lives on `/users/`).

**Context added for this role:**

| Key | Type | Source |
|---|---|---|
| `admin` | dict | `admin_dashboard(user)` |
| `admin.users_total` / `users_active` | int | `User.objects` counts |
| `admin.releases_total` / `releases_open` | int | `Release.objects` counts |
| `admin.ec_total` / `ec_pending_review` | int | `EC.objects` counts (`IN_VALIDATION`) |
| `admin.actions_today` | int | `LogEntry` where `timestamp__date = today` |
| `admin.recent_logs` | list[dict] | 5 newest `LogEntry` → `{time, description}` |
| `log_table` | `ActivityTable` | built from `admin.recent_logs`, `request` passed for django-tables2 |

**Output:**

| Case | Status | Result |
|---|---|---|
| Administrator | 200 | Header, 4 KPI cards, `Atividade recente`, `Ver todos os logs` |
| Non-administrator (any other role) | 200 | Own dashboard; `admin` and `log_table` **absent** from context |
| Anonymous | 302 | → `/` (`LOGIN_URL`) |

**Feed sentence grammar** (`_log_activity`, all Portuguese):

| Row | Renders as |
|---|---|
| `DocumentVersion` create | `Maria da Costa enviou a v1.0 do EC 2026-012` |
| `Review` decision approved | `João Soares aprovou o EC 2026-005` |
| `Review` decision rejected, has comment | `João Soares rejeitou o EC 2026-009 com comentário` |
| `User` create (after PR #70) | `Admin criou o utilizador lusia.gusmao` |
| `EC` create | `Admin criou o EC 2026-012` |
| `EC` status change | `… alterou o EC 2026-012 → Enviada para DES` |
| Anything else | `verb + object_repr`, verb from `CREATE/UPDATE/DELETE` |

`time` is `HH:MM` in `TIME_ZONE` (`Asia/Dili`).

## Edge Cases

1. **No logs at all** → `ActivityTable.empty_text` renders `Sem atividade registada.`, never a blank card.
2. **`LogEntry.actor is None`** (row written outside an HTTP request) → the sentence opens with
   `Sistema`, not an empty name or `None`.
3. **More than 5 logs** → exactly the 5 newest. It is a `[:5]` slice, not pagination: the panel has
   no page control by design; full detail is one click away.
4. **`object_repr` without an EC code** (Release, User rows) → the sentence falls back to the raw
   `object_repr`; no `IndexError`, no stray `None`.
5. **Rejected review with an empty comment** → no trailing ` com comentário`.
6. **Everything zero** (fresh DB) → KPI cards show `0`; this panel computes no percentages, so
   division by zero cannot occur here.
7. **Other roles pay nothing** → the admin block is an `elif`, so `admin_dashboard()` is never
   called for requester/CD/DES (no extra queries, no user data outside the admin panel).

## Project Structure

See System Architecture above. Six files changed; no new file outside the spec itself.

## Code Style

Thin view (§6), wording and queries in the selector (§5).

```python
# selectors.py
def admin_dashboard(user) -> dict:
    log_qs = LogEntry.objects.select_related("actor", "content_type")
    return {
        "users_total": User.objects.count(),
        ...
        "actions_today": log_qs.filter(timestamp__date=today).count(),
        "recent_logs": [_log_activity(e) for e in log_qs.order_by("-timestamp")[:5]],
    }
```

```python
# views.py
elif self.request.user.role == "administrator":
    context["admin"] = admin_dashboard(self.request.user)
    context["log_table"] = ActivityTable(context["admin"]["recent_logs"], request=self.request)
```

```python
# tables.py
class ActivityTable(tables.Table):
    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Sem atividade registada."
```

Both table columns are `orderable=False` — the rows arrive sorted by the selector.

## Testing Strategy

TDD: failing test first. Same module (`test_dashboard.py`), same `pytestmark` + `class Test...:`
style as the rest of the file.

| # | Test | Proves |
|---|------|--------|
| 1 | `test_admin_sees_header_kpis_users_and_activity` | header, all 4 KPIs, feed, table headers, no search box |
| 2 | `test_non_admin_does_not_see_the_admin_panel` | no admin text leaks to another role |
| 3 | `test_the_user_list_stays_out_of_the_dashboard` | the user list lives only on `/users/` |
| 4 | `test_counts_match_the_database` | every KPI equals its query, release shared by both ECs |
| 5 | `test_recent_logs_come_from_auditlog` | feed reads `LogEntry`, `actions_today`, `HH:MM` |
| 6 | `test_an_upload_reads_as_one_portuguese_sentence` | real sentence via `set_actor()` |
| 7 | `test_the_feed_is_limited_to_the_five_latest_entries` | `[:5]` slice holds |
| 8 | *(planned)* `test_empty_feed_shows_the_portuguese_placeholder` | edge case 1 |
| 9 | *(planned)* `test_log_without_an_actor_reads_as_sistema` | edge case 2 |

Tests 8 and 9 are **required by this spec** and are the remaining work on this branch — edge cases
1 and 2 are otherwise only asserted by hand.

`TestRolePlaceholders` keeps its two surviving tests (unknown role, login redirect); the
administrator row was removed because the placeholder it asserted no longer exists.

## Boundaries

- **Always:** TDD, `uv run pytest -q` + `uv run ruff check .` before done, queries in `selectors.py`,
  thin view, all UI strings in Portuguese.
- **Read-only:** the panel renders counts and a log; it performs no POST, no mutation, no export.
- **Status untouched** — `EC.status` may only change through `workflow` services (§6); nothing here
  offers a status control.
- **No user table on this page** — the list, its search and its buttons live on `/users/`
  (`ACCOUNTS_USER_LIST.md`).
- **No chart for admin.** A 7-day line chart was built and then deliberately removed (see Decisions);
  do not reintroduce a canvas, payload or Chart.js block for this role without a new decision.
- **Ask first:** new dependencies, any change to `accounts.User` or a migration, changing the feed's
  wording rules, moving `auditlog.register` calls out of `admin.py`.

## Success Criteria

- [ ] Opening `/backlog/dashboard/` as an administrator shows the header, 4 KPI cards and the feed.
- [ ] Every KPI number equals its selector query on a seeded database.
- [ ] The feed renders 5 rows as Portuguese sentences with `HH:MM`, or the empty placeholder.
- [ ] No other role ever receives `admin` or `log_table` in its context.
- [ ] No canvas, no `json_script` payload and no Chart.js branch exists for the administrator.
- [ ] Full suite green (`218 passed` as of 2026-10-22, plus tests 8 and 9); `ruff check .` clean.

## Decisions (resolved 2026-10-22)

1. **Own spec, not an amendment to `DASHBOARD.md`.** That spec is approved and scoped to other roles;
   merging admin into it would rewrite an approved document for an unrelated audience.
2. **Text feed, not a line chart.** A 7-day, 3-series line chart (`Criou`/`Alterou`/`Removeu`) was
   implemented and removed at the user's request: "aktivitas recente bisa, line chart tidak". The
   `json_script` payload, canvas and `whenPresent` block were deleted with it — no dead JS left.
3. **Feed rendered by django-tables2 (`ActivityTable`)**, not a hand-rolled `<ul>`, so it matches
   every other table in the dashboard and inherits its empty state.
4. **Feed capped at the 5 newest rows**; per-row detail belongs to a future `Registo de Auditoria`
   page (sidebar link is still `href="#"`), and today's fallback is the auditlog changelist.
5. **No avatar chip.** The reference mockup had one top-right; the user chose to keep
   `Sessão iniciada como …` instead.
6. **No user table.** It was first built here, then moved to `/users/` at the user's request; the
   dashboard keeps only the `Utilizadores` KPI card.
7. **`auditlog.register(User)` is out of this branch** — it ships with PR #70 so that this PR stays
   dashboard-only.

## Open Questions

- **Registration lives in `admin.py`.** All five `auditlog.register(...)` calls sit in `admin.py`
  modules, which only import on admin autodiscovery (URLconf load). A management command writing
  rows before any request would not be logged. Is moving them to `apps.py` worth it? Not addressed
  by this spec; needs a decision.
- **User names in the feed** come from `LogEntry.object_repr`, which is `str(User)` = username.
  Showing full names would need either a `User.__str__` change (touches `accounts.User`, out of scope
  here) or an extra lookup. Currently renders `Admin criou o utilizador lusia.gusmao`.

## Branch Name

`feat/admin-dashboard` (PR #69)
