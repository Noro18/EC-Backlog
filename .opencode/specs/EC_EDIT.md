# Spec — Edit an existing EC (issue #67)

## Objective

`GET|POST /backlog/detail_ec/<pk>/editar/` lets the owner correct the **content** of an EC that is
still in flight, without minting a second EC.

- As the requester who created an EC, I open *Editar* from the detail page and fix a typo in the
  `reference`, rewrite the `description`, or move the EC to another open Release.
- As the requester, I see the form pre-filled with what is saved today, so I change one field and
  leave the rest untouched.
- As the requester, when I save I return to the detail page and see my new values plus a success
  message.
- As a CD, a DES user, or a requester who does not own this EC, I get **403** on both GET and POST —
  the button being hidden in HTML is not the gate.
- As a user with a stale tab, I cannot save an edit that the lifecycle no longer allows: the status
  is re-checked in the service, and a race surfaces as a form error, never a 500.

**Why this exists — SRD mapping.** The SRD has no RF for *free editing* of an EC; this issue is
explicit that it needs a product decision. What the SRD does anchor: RF01 (identity is generated and
immutable), RF02 (an EC may be associated with an **open** Release, one-to-many, capacity 10),
RF03 (`creation_date` recorded at submission), RF07 (`responsible_cd` is its own step), RNF02 (every
change is audited with user + timestamp), RNF05 (usable UI). The gaps are marked as decisions below
and need confirmation before code.

**Out of scope:** `status` (workflow services only), `year` / `number_sequence` (identity), the
document (RF05 already versioned), `responsible_cd` (RF07), `requester` reassignment, deleting an
EC, bulk edit from the list, creating a new Release from the edit form (RF02 on-demand stays on the
create form), and any DB constraint on `reference` (issue #36).

## Assumptions

1. The EC already exists and is visible to the acting user through the existing rules; this slice
   adds a write path, not new visibility.
2. `EC.status` may only be changed by `apps/workflow/services.py` (`ARCHITECTURE.md §6`). This slice
   never assigns it, directly or through a form field.
3. `auditlog.middleware.AuditlogMiddleware` is already installed (`config/settings/base.py:72`) and
   `EC` is registered (`apps/backlog/admin.py:48`), so a normal `.save()` records the actor —
   proven by `apps/backlog/tests/test_auditlog.py:17`.
4. Baseline on this branch (`feat/edit-ec` from `upstream/main` = `1cab42c`, PR #73 merged):
   **242 tests green**.
5. The UI language is Portuguese; code, comments and this spec are English.

## Decisions (proposed 2026-10-23 — confirm before code)

1. **Editable fields: `reference`, `description`, `release` — nothing else.**
   `creation_date` is excluded: RF03 says it is recorded at submission (a fact, not content), and
   letting anyone re-date an EC would falsify the backlog history. `requester` and
   `responsible_cd` are excluded because the issue lists them as separate steps
   (`workflow:resubmit_ec` already reassigns the CD when a rejected EC is resubmitted).
   `status`, `implemented_at`, `year`, `number_sequence`, `is_imported` are never exposed.
2. **Who may edit: the owning requester, or an Administrator.** CD cannot (RF09: the CD's role ends
   at approve/reject); DES cannot; another requester cannot. *This needs confirmation*: SRD §4 gives
   the Administrator "users, profiles and numbering parameters" and calls the dedicated admin
   profile "to be confirmed", so admin-edit is a proposal, not a requirement. Note that
   `NewECView` already allows `requester` + `administrator` to create, and an imported EC has
   `requester = NULL` — without admin edit, nobody could ever fix one.
3. **Which statuses allow editing: `in_validation` and `rejected` only.**
   Those are the two states where the content is still being shaped. `approved`/`sent_to_des`/
   `closed` are refused: the CD approved a document against that content, and moving a closed EC to
   another Release would rewrite the history that RF11 just closed. `cancelled` is terminal.
4. **A Release change must target an open Release with a free seat — but the current Release always
   stays selectable**, even if it is now full or closed, so "save without touching the Release"
   never fails. Capacity is checked only when the target differs from the current Release.
   The edit form never creates a Release and never closes/reopens one (RF11 owns that).
5. **`ECEditForm` is a separate `ModelForm`, not a reuse of `ECCreateForm`.** Why: the create form
   owns the document upload (RF06), the CD assignment (RF07) and the `__new__` Release sentinel
   (RF02) — none of which belong here, and reusing it would silently widen this slice.
6. **Rules live in `services.py`; the view orchestrates.** New `update_ec(ec, user, *, reference,
   description, release)` plus a pure predicate `can_edit_ec(ec, user)` used by the detail page and
   by the update view's `test_func` (`ARCHITECTURE.md §5`, thin views).
7. **Forbidden = 403, not a redirect**, matching `NewECView`, `ReviewECView` and `RouteToDESView`.
   Anonymous still redirects to login (`LoginRequiredMixin`).
8. **Success goes back to the EC detail page**, because that is where the user came from; the list
   would lose the context of what was just repaired.
9. **No schema change, no migration.** `reference` uniqueness stays issue #36, untouched.
10. **No POST-only trick needed**: this is a normal form view (GET renders, POST saves), unlike
    `go_live`/`route_to_des` which are single-action POSTs.

## Tech Stack

Django 6.1 class-based views, `ModelForm`, Bootstrap 5. **No new dependency** and no new app.
`auditlog` already provides RNF02.

## Commands

```bash
uv run pytest apps/backlog/tests/test_services.py -q
uv run pytest apps/backlog/tests/test_views.py -q
uv run pytest -q                       # 242 -> ~259
uv run ruff check .
uv run python manage.py runserver      # manual: detail page -> Editar
```

## System Architecture

```
apps/backlog/
├── forms.py        # + ECEditForm (reference, description, release)
├── selectors.py    # + releases_for_edit(current_release)
├── services.py     # + can_edit_ec(ec, user), update_ec(...)
├── views.py        # + ECUpdateView; ECDetailView.get_context_data adds `can_edit`
├── urls.py         # + detail_ec/<int:pk>/editar/  name="ec_edit"
└── tests/
    ├── test_services.py   # + class TestUpdateEC
    ├── test_views.py      # + class TestECEditView
    └── test_auditlog.py   # + one update-actor test
templates/backlog/
├── ec_detail.html  # + "Editar" button (only when `can_edit`)
└── ec_edit.html    # NEW — pre-filled form, Cancelar -> detail
```

Import direction is untouched: everything stays inside `backlog`, which imports only
`accounts` (downward). No `workflow` and no `documents` import is introduced.

## Database Schema Changes

**None.** No model field, constraint, index or migration. Confirmation that nothing is needed:

- `reference` — `CharField(max_length=50)`, form validates length and required (`models.py:66`).
- `description` — `TextField`, required in the form (`models.py:67`).
- `release` — nullable FK (`models.py:75`); the form requires it, the model stays permissive for
  imported history.
- Identity `UNIQUE(year, number_sequence)` (`models.py:98`) is never written by this slice.
- RNF02 audit comes from the existing `auditlog` registration (`admin.py:45-48`).

## Input / Output

**GET** `backlog:ec_edit` (`/backlog/detail_ec/<pk>/editar/`)

| Case | Result |
|---|---|
| anonymous | 302 → login |
| owner in `in_validation` / `rejected` | 200, form pre-filled with `reference`, `description`, `release` |
| Administrator (any editable status) | 200, same form |
| CD / DES / non-owner requester | 403 |
| owner but `approved` / `sent_to_des` / `closed` / `cancelled` | 403 |
| unknown pk | 404 |

**POST** same URL

| Case | Result |
|---|---|
| valid | 302 → `backlog:ec_detail`, `messages.success("EC {code} atualizada.")` |
| `reference` empty or > 50 chars | 200, field error, nothing written |
| `description` empty | 200, field error, nothing written |
| `release` missing / closed / full (and different) | 200, error on `release` (or non-field), nothing written |
| `release` = current, even if full/closed | saves the other fields |
| POST contains `status=closed`, `year=1999`, `number_sequence=1` | ignored — not in the form's field list |
| status changed between GET and POST (race) | 200, non-field error "no longer editable", nothing written |
| not allowed at all | 403 |

**Release dropdown** = open Releases with a free seat **plus** the EC's current Release. Labels must
not lie: the current Release may be shown as full/closed, so the label reflects that state rather
than always saying "aberta". No `__new__` option.

## Edge Cases

1. **Current Release is full (10/10) or already closed.** Still listed and still valid, because the
   EC already holds its seat; the capacity rule applies to *new* seats, not to keeping one.
2. **Target equals current Release.** Treated as "no move": no capacity query, no error.
3. **Target Release is full or closed.** Refused inside the service with a `ValidationError`, even
   if the HTML was tampered with.
4. **Race on capacity.** The service re-reads the target Release inside `transaction.atomic()` and
   re-checks `ec_count >= capacity or not is_open`. On SQLite the whole-file write lock serialises
   the two writes; do not claim a concurrency proof (`ARCHITECTURE.md §7`).
5. **Race on status.** Status re-checked in the service, after the form was rendered. A stale tab
   gets a form error, not a 500 and not a silent write.
6. **No Release at all** (imported EC). The dropdown starts empty; saving requires choosing an open
   Release. Accepted: imported rows are historically `closed`, so Decision 3 already blocks this
   path; if the import later maps them to `in_validation`, attaching a Release is exactly what they
   need.
7. **EC with `requester = NULL`** (imported). Only the Administrator passes `can_edit_ec`.
8. **Whitespace text.** Django `CharField`/`TextField` strip surrounding whitespace; `"   "` becomes
   empty and is refused as blank.
9. **Same values submitted.** Saves are idempotent; `update_fields` is used, and auditlog records
   only real changes (no phantom UPDATE row).
10. **Unknown/extra POST keys** are ignored by `ModelForm` (whitelisted `fields`), so `status` cannot
    be smuggled in.
11. **`pk` of another user's EC.** 403 before any query on the form's data; no information leak
    beyond the 404/403 distinction already used elsewhere.

## Code Style

```python
# services.py
EDITABLE_STATUSES = (EC.Status.IN_VALIDATION, EC.Status.REJECTED)


def can_edit_ec(ec, user) -> bool:
    """Owner (or Administrator) while the content is still in flight."""
    if ec.status not in EDITABLE_STATUSES:
        return False
    return user.role == User.Role.ADMINISTRATOR or ec.requester_id == user.pk


def update_ec(ec, user, *, reference, description, release):
    if not can_edit_ec(ec, user):
        raise PermissionDenied("This EC cannot be edited.")
    with transaction.atomic():
        if release is not None and release.pk != ec.release_id:
            fresh = Release.objects.get(pk=release.pk)
            if not fresh.is_open or fresh.ec_count >= fresh.capacity:
                raise ValidationError("Release EC limit reached or release is closed.")
            ec.release = fresh
        ec.reference = reference
        ec.description = description
        ec.save(update_fields=["reference", "description", "release"])
    return ec
```

```python
# views.py — thin
class ECUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = EC
    form_class = ECEditForm
    template_name = "backlog/ec_edit.html"

    def test_func(self):
        return can_edit_ec(self.get_object(), self.request.user)
```

## Testing Strategy

TDD: failing test first. Same conventions as the existing modules — `pytestmark =
pytest.mark.django_db`, one `class Test...:` per behaviour, data from `apps/backlog/tests/factories.py`.

| # | Test | Proves |
|---|------|--------|
| 1 | owner updates reference + description | happy path |
| 2 | owner moves the EC to an open Release with room | RF02 |
| 3 | non-owner requester denied | Decision 2 |
| 4 | CD denied | Decision 2 |
| 5 | DES denied | Decision 2 |
| 6 | administrator allowed (proposed) | Decision 2 |
| 7 | `approved` EC denied | Decision 3 |
| 8 | `closed` EC denied | Decision 3 |
| 9 | move to a full Release refused | edge 3 |
| 10 | move to a closed Release refused | edge 3 |
| 11 | keeping a full current Release works | edge 1 |
| 12 | GET pre-fills the form | UX |
| 13 | form exposes only the three fields | Decision 1 |
| 14 | POST redirects to detail + message | Decision 8 |
| 15 | POST smuggled `status` is ignored | edge 10 |
| 16 | anonymous GET → login | auth |
| 17 | update writes a `LogEntry` with the actor | RNF02 |
| 18 | 403 also from the detail *button* context (`can_edit=False`) | Decision 2 |

Expected suite: **242 + 18 = 260**.

## Boundaries

- **Always:** TDD, `uv run pytest -q` + `uv run ruff check .` before done, service owns rules,
  status untouched, PT UI labels, audit via existing registration.
- **Ask first:** allowing the CD to edit, allowing edits after `approved`, letting `reference`
  become the unique key (#36), any migration, adding "delete EC", adding a "new Release" option to
  the edit form.
- **Never:** write `ec.status` here, expose `year` / `number_sequence` / `is_imported`, import
  `workflow` or `documents` from `backlog`, route by POST-only without stating it, `git add .` over
  the untracked `apps/workflow/management/*` files.

## Success Criteria

- [ ] *Editar* appears on the detail page only for an owner (or admin) in an editable status.
- [ ] The form is pre-filled and contains exactly `reference`, `description`, `release`.
- [ ] Saving returns to the detail page with the new values and a success message.
- [ ] `year`, `number_sequence`, `status`, `creation_date`, `implemented_at`, `requester`,
      `responsible_cd` are not editable anywhere in the form or the POST.
- [ ] A closed/full target Release is refused with a clear message; keeping a full current Release
      works.
- [ ] Non-owner, CD, DES and terminal-status ECs get 403, never 500.
- [ ] A `LogEntry` with `action=UPDATE` and the acting user is written (RNF02).
- [ ] 260 tests green, `ruff check .` clean, no migration generated.

## Deferred

- **Changing the requester** and **changing `responsible_cd`** from a general edit form (RF07 has
  its own step; resubmission already reassigns the CD).
- **Editing after `approved`** — if the business wants a "correction after approval" path, it should
  be a workflow transition with its own audit, not a silent field update.
- **Cancelling / deleting an EC.**
- **Bulk edit** from the EC list.
- **Optimistic locking** (e.g. `updated_at` check) — SQLite plus single-team usage makes the status
  and capacity re-checks sufficient for now.

## Open Questions

- **Administrator as editor** — proposed above (Decision 2) because imported ECs have no requester.
  SRD §4 leaves the dedicated admin profile "to be confirmed". Confirm or drop.
- **`rejected` ECs** — editing fields is allowed here, but RF05/RF09 also allow "correct and
  resubmit" with a new document version. Do we want both paths, or should a rejected EC only be
  edited through resubmission?
- **Should `creation_date` ever be correctable** (e.g. an EC submitted offline earlier)? Excluded
  now; RF03 treats it as a record.

## Branch Name

`feat/edit-ec`
