# Spec — User creation form (`.opencode/specs/USER_CREATE.md`)

## Objective

Give an Administrator a form to create a user **inside** `Gestão de Utilizadores`, so they no longer
have to leave the app for `/admin/accounts/user/add/`.

- As an administrator, I fill in `username`, `name`, `email`, profile (`role`), state and an initial
  password (twice) and land back on the user list with the new row and its badge.
- As an administrator, I see every label in Portuguese and every invalid field marked where I typed it.
- As a non-administrator or a visitor, I never reach the form (403 / 302) and no row is ever written.

> **Scope:** this is the *create* part of issue #68 only. Edit and delete/deactivate are **Deferred**
> (see below) and need their own specs — the decisions this document records are what unblocks them.

## Assumptions

1. No self-registration (the SRD says nothing about it — issue #68 assumes no).
2. Django's `/admin/` stays reachable and unchanged; this form is an addition, not a replacement.
3. `auditlog.register(User)` already lives in `apps/accounts/admin.py` (PR #70) and Django's
   `AdminConfig.ready()` runs `autodiscover()` at startup — so any `User` row our form saves is
   logged automatically (RNF02), with no `LogEntry` writing in our code.
4. `LOGIN_URL = "accounts:login"`, `LANGUAGE_CODE = "en-us"` (`config/settings/base.py:125,161`).
5. Baseline on this branch (`feat/user-create-form`, `upstream/main` = `fd178f9`): **227 tests green**.

## Decisions (agreed 2026-10-22)

1. **The administrator types the initial password** — `password1` + `password2` from Django's
   `UserCreationForm`, so hashing and the `AUTH_PASSWORD_VALIDATORS` rules (min length 8,
   common-password list) apply for free.
   *Rejected:* an unusable password — issue #68 puts email-based reset out of scope, so the account
   would be dead on arrival and we'd be back to Django admin. *Rejected:* an auto-generated password
   — it needs a one-time display surface and a channel to hand it over, neither of which exists.
2. **`username` is immutable after creation.** Required and unique at creation (Django's own rules —
   no invented format rule), and the future edit form must show it read-only. Why: it is the login
   identity *and* the string that `LogEntry.object_repr` puts into the `Painel do Administrador`
   activity feed; editing it would silently rewrite how history reads.
3. **No in-app delete; deactivation only** (`is_active=False`). `EC.requester` and
   `EC.responsible_cd` are `on_delete=PROTECT`, so deleting a user who owns or is assigned ECs raises
   `ProtectedError`; deactivating keeps the EC history and the audit trail intact while blocking
   login. Permanent deletion stays a deliberate act in Django admin.
4. **The *Novo Utilizador* button repoints to this form; the *Editar* column keeps pointing at
   Django admin** for now (`tables.py:44`). A button that leads nowhere in-app would be worse than
   the status quo; *Editar* moves when the edit spec lands.
5. **Validation lives in the form, saving lives in `services.create_user()`** — same split as
   `EC_CREATE.md` Decision 1. The view stays a `CreateView` that only gates and wires.
6. **`role` is required — no empty choice.** Choices come from `User.Role` exactly (RNF01's four
   profiles, nothing invented); the model's `default=REQUESTER` is not used as a form fallback, so a
   profile can never be "forgotten".
7. **`name` is required in the form** even though the model allows `blank=True` — imported history has
   empty names, a user created here is typed by a human. Same pattern as `ECCreateForm` making
   `release`/`responsible_cd` required although the model allows null.
8. **Labels and help text are Portuguese (we author them); Django's built-in error strings stay as
   shipped.** `LANGUAGE_CODE = "en-us"`, so messages like *"The two password fields didn't match."*
   arrive in English. Translating them means either a global `LANGUAGE_CODE` change (touches admin
   and emails) or a per-field `error_messages` dict — both out of scope here, recorded in *Open
   Questions*.

## Tech Stack

Django 6.1, `django.contrib.auth.forms.UserCreationForm` (stdlib), `django-auditlog` (already
registered), factory-boy.
**No new dependency, no migration.**

## Commands

```bash
uv run pytest apps/accounts/tests -q    # feature tests
uv run pytest                           # full suite (227 → 241)
uv run ruff check .                     # lint
uv run python manage.py runserver       # manual check as an administrator
```

> `uv run ruff format .` is **not** part of the done-check (pre-existing files are unformatted) —
> same note as `ACCOUNTS_USER_LIST.md`.

## System Architecture

```
apps/accounts/
├── forms.py      # NEW  UserCreateForm(UserCreationForm) — validation + Portuguese labels
├── services.py   # NEW  create_user(form) — the only place that writes a User row
├── views.py      # EDIT UserCreateView (LoginRequiredMixin + UserPassesTestMixin, like UserListView)
├── urls.py       # EDIT path("users/novo/", ..., name="user_create")
├── tables.py     # UNCHANGED (Editar column still → Django admin, Decision 4)
├── admin.py      # UNCHANGED (auditlog registration stays there)
├── models.py     # UNCHANGED — no migration
└── tests/
    ├── test_forms.py   # NEW  form-level validation tests
    └── test_views.py   # EDIT gate, save, audit, button tests

templates/accounts/user_form.html   # NEW mirrors ec_form.html markup
templates/accounts/user_list.html   # EDIT line 20: button → accounts:user_create
.opencode/specs/USER_CREATE.md      # this file
```

Import direction (§5): everything new lives inside `apps/accounts` and imports only Django plus its
own `models` — the bottom of the graph, so nothing can point upward.
`apps.backlog.forms` already imports `accounts.models` (downward) and stays untouched.

## Database Schema Changes

**None.** No model edit, no migration, no new constraint.
`is_active` (with its `Ativo`/`Inativo` badge in `UserTable`), `email unique=True` and the four
`User.Role` choices already exist.

## Input / Output

**Input:** GET/POST `/users/novo/`.

| Case | Method | Status | Result |
|---|---|---|---|
| Administrator, valid data | POST | 302 → `accounts:user_list` | row exists, badge correct, password hashed |
| Administrator, valid data | GET | 200 | form with Portuguese labels |
| Administrator, invalid data | POST | 200 | same template, field errors, **0 rows** |
| Any other role | GET/POST | 403 | **0 rows** |
| Anonymous | GET | 302 → `accounts:login` | — |
| Anonymous | POST | 302 → `accounts:login` | **0 rows** (mixin runs before `form_valid`) |

**Fields:**

| Field | Where it comes from | Required | Validation |
|---|---|---|---|
| `username` | `UserCreationForm` | yes | unique, ≤150 (model/Django rules) |
| `name` | our field, label `Nome` | yes (Decision 7) | ≤150 |
| `email` | our field, label `Email` | yes | unique, Django email format |
| `role` | our field, label `Perfil` | yes (Decision 6) | exactly the four `User.Role` values |
| `is_active` | our field, label `Estado` | no — checkbox defaults to on | — |
| `password1` / `password2` | `UserCreationForm`, labels `Palavra-passe` / `Confirmar palavra-passe` | yes | must match; `AUTH_PASSWORD_VALIDATORS` (min 8 + common passwords) |

Errors render exactly like `ec_form.html:29`:
`{% for error in form.X.errors %}<div class="text-danger small mt-1">{{ error }}</div>{% endfor %}`
plus `is-invalid` on the input, as `login.html:36` does.

## Edge Cases

1. **Duplicate email** → field error from the ModelForm's unique validation; never an `IntegrityError`
   500 (email is `unique=True` and the model's own validation runs in `full_clean`).
2. **Duplicate username** → same: field error, no row.
3. **Password too short, too common, or mismatched** → field error on `password1`/`password2`;
   nothing reaches the database.
4. **`role` left empty** → field error; the model default must not silently make someone a
   *Requester*.
5. **`name` left empty** → field error (form contract, Decision 7).
6. **`is_active` unchecked at creation** → the row is created `Inativo`, shows the grey badge in the
   list, and cannot log in. Allowed, not an error.
7. **Anonymous POST** → redirected to login with **zero rows written**; the gate must run before any
   save.
8. **Non-administrator POST** → `403`, zero rows.
9. **No normalization is invented** — the SRD says nothing about case, so `"Ana"` and `"ana"` are
   different usernames and `"a@b.com"` ≠ `"A@b.com"`: plain database behaviour, no lowercasing added.
10. **Two simultaneous POSTs with the same username** — form-level uniqueness has a check-then-save
    window, so a true race could still raise `IntegrityError`. Accepted for a single-administrator
    screen; revisit only if an import/bulk path ever appears (then catch it and surface a
    `non_field_errors` message).

## Project Structure

See *System Architecture*. Six files touched, two new code files, one new template, one new test
module. Nothing outside `apps/accounts`, `templates/accounts` and `.opencode/specs`.

## Code Style

```python
# forms.py — validation lives here, saving lives in the service (Decision 5)
class UserCreateForm(UserCreationForm):
    """USER_CREATE.md: Portuguese labels, `role` required, `name` required."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "name", "email", "role", "is_active")
        labels = {"name": "Nome", "email": "Email", "role": "Perfil", "is_active": "Estado"}

    # ...widgets set class="form-control"/"form-select", as backlog/forms.py does
```

```python
# services.py — the only place a User row is created
def create_user(form: UserCreateForm) -> User:
    """RNF02: the auditlog signal registered in admin.py records actor and time."""
    return form.save()          # UserCreationForm.save() hashes the password
```

```python
# views.py — gate + wiring only
class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def test_func(self):
        return self.request.user.role == "administrator"

    def form_valid(self, form):
        create_user(form)
        return super().form_valid(form)
```

```python
# urls.py
path("users/novo/", UserCreateView.as_view(), name="user_create"),
```

```html
<!-- templates/accounts/user_list.html:20 -->
<a href="{% url 'accounts:user_create' %}" class="btn btn-sm btn-primary">
```

## Testing Strategy

TDD: write the failing test first. New module `test_forms.py` plus additions to `test_views.py`,
both keeping the repo's `pytestmark = pytest.mark.django_db` + `class Test...:` style. Assertions
target **field keys** (`form.errors["role"]`), never Django's English message text, so the suite
stays correct if the language question is ever answered (Decision 8).

| # | Test | Proves |
|---|------|--------|
| 1 | `test_a_complete_form_is_valid` | happy path at form level |
| 2 | `test_mismatched_passwords_are_rejected` | `password2` error |
| 3 | `test_passwords_shorter_than_eight_characters_are_rejected` | `AUTH_PASSWORD_VALIDATORS` runs |
| 4 | `test_a_duplicate_username_is_rejected` | edge case 2 |
| 5 | `test_a_duplicate_email_is_rejected` | edge case 1 |
| 6 | `test_the_profile_is_required` | edge case 4 / Decision 6 |
| 7 | `test_the_name_is_required` | edge case 5 / Decision 7 |
| 8 | `test_administrator_sees_the_form_with_portuguese_labels` | GET 200, `Perfil`, `Palavra-passe` |
| 9 | `test_administrator_creates_a_user_and_returns_to_the_list` | POST 302, row + badge |
| 10 | `test_the_created_password_is_hashed_and_can_log_in` | `identify_hasher` + real login |
| 11 | `test_the_created_user_reaches_the_audit_log` | RNF02: `LogEntry`, actor = session user |
| 12 | `test_non_administrator_gets_403_and_creates_nothing` | edge case 8 |
| 13 | `test_anonymous_post_redirects_to_login_and_creates_nothing` | edge case 7 |
| 14 | `test_an_invalid_post_re_renders_with_errors_and_creates_nothing` | edge case 3 |
| 15 | `test_the_novo_utilizador_button_points_at_the_app_form` | Decision 4 repoint |

Expected suite: **241 = 227 + 15**.

## Boundaries

- **Always:** TDD, `uv run pytest -q` + `uv run ruff check .` before done, queries/writes in
  `services.py`, gate identical to `UserListView` (`role == "administrator"`), Portuguese labels.
- **Ask first:** the edit or delete form, any password reset/change flow, self-registration, moving
  `auditlog.register(...)`, changing `User.__str__` or `full_name`, exposing `first_name`/`last_name`,
  changing `LANGUAGE_CODE` to translate Django's messages, repointing the *Editar* column, any new
  dependency.
- **Never:** a migration or a change to `accounts.User`, removing Django admin access, touching
  `templates/base.html`, inventing username/email format rules the SRD does not state, bulk
  create/delete.

## Success Criteria

- [ ] An administrator creates a user from `/users/novo/` and it appears in the list with the right
      role and state badges.
- [ ] The stored password is hashed and that user can log in.
- [ ] Duplicate username/email, a short password, or an empty profile all re-render with a field
      error and write **zero** rows — never a 500.
- [ ] Non-administrator → 403; anonymous → 302; in both cases zero rows.
- [ ] A `LogEntry` row exists for the creation, with `actor` = the administrator (RNF02).
- [ ] *Novo Utilizador* opens our form; *Editar* still opens Django admin.
- [ ] `git status` shows **no migration** and no change to `models.py`/`admin.py`/`base.html`.
- [ ] 241 tests green, `ruff check .` clean.

## Deferred

- **Edit form** (name, email, profile, state; `username` read-only per Decision 2).
- **Delete vs deactivate UI** — Decision 3 already answers the direction: deactivate only.
- **Password reset by an administrator.**
- **Repointing the *Editar* column** off Django admin.
- **Portuguese translation of Django's built-in validation messages.**

## Open Questions

- **May an administrator create another `administrator`?** The choices come from `User.Role`, which
  includes it, and RNF01 lists four profiles — but SRD §4 says the dedicated Administrator profile
  is *"need for a dedicated profile to be confirmed"*. Not resolved by guessing: confirm before
  treating the fourth choice as settled.
- **`UserFactory` upward import (carried over).** `test_forms.py` will import `UserFactory` from
  `apps.backlog.tests.factories` like its siblings — still the undecided item from
  `ACCOUNTS_USER_LIST.md` (local `accounts/tests/factories.py` vs accepting test-only imports).
- **Race guard for duplicate usernames** (edge case 10): accept as-is, or add an `IntegrityError`
  → `non_field_errors` handler now?

## Branch Name

`feat/user-create-form`
