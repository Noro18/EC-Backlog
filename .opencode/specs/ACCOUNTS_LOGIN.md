# Spec: Login / Logout (accounts)

## Objective

Give the application its own login and logout flow so pages can be reached with a real session.
Right now `templates/accounts/login.html` is empty, `apps/accounts/views.py` is a placeholder, and
`apps/accounts/urls.py` does not exist. The only way in is `/admin/`.

- As a user, I go to `/accounts/login/` and sign in with username and password.
- As a user, I am sent back to where I originally wanted to go after signing in.
- As a user, I can sign out and my session is destroyed.
- As a visitor, I am bounced to the login page when I open a protected page.

**Out of scope:** registration, password reset, email confirmation, "remember me", social login,
role-based permissions on individual views (that comes with the pages themselves), MFA.

## Tech Stack

Django's built-in `AuthenticationForm` + `LoginView` + `LogoutView`. No new dependency.
`AUTH_USER_MODEL = "accounts.User"` is permanent (ARCHITECTURE.md §8) — not touched.

## Commands

```bash
uv run pytest apps/accounts/tests/test_views.py   # feature tests
uv run pytest                                     # full suite
uv run ruff check . && uv run ruff format .       # lint
uv run python manage.py runserver                 # manual check at /accounts/login/
```

## System Architecture

Three changes, all additive:

1. `apps/accounts/urls.py` (new) — `login/` and `logout/` routes, `app_name = "accounts"`.
2. `apps/accounts/views.py` — one `LoginView` subclass for the Portuguese template name and
   `redirect_authenticated_user`, plus a logout view.
3. `config/urls.py` — `include("apps.accounts.urls")`.

Plus settings and the template. Views stay thin: Django's class-based views do the work, we only
supply configuration. No `services.py` needed — authentication is framework behaviour, not a domain
rule.

## Database Schema Changes

**None.** `accounts.User` already exists (`username`, `password`, `role`, `is_staff`, `is_active`).
Sessions are stored in Django's `django_session` table, already migrated.

No migration is created by this feature.

## Settings Changes

```python
# config/settings/base.py
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "backlog:ec_list"
LOGOUT_REDIRECT_URL = "accounts:login"
```

Defaults are deliberately kept. Not touched:

- `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY` — already at Django defaults.
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` — must stay `False` for local HTTP dev. These
  become `True` in production per ARCHITECTURE.md §11.

## Template

`templates/accounts/login.html` extends `base.html`, posts to `accounts:login`, renders
`{{ form.as_div }}` inside a Bootstrap card. Labels come from Django's auth form, already Portuguese
via `get_user_model().USERNAME_FIELD` — we set Portuguese labels explicitly on the form subclass.
Portuguese UI text: "Entrar", "Utilizador", "Palavra-passe", "Entrar na aplicação", "Saiu da
aplicação com sucesso."

## Input / Output

**Login form fields**

| Field | Source | Validation |
|---|---|---|
| `username` | `accounts.User.username` | `max_length=150`, required, exact match |
| `password` | `accounts.User.password` | required, checked by Django's hasher |

**Responses**

| Case | Status | Result |
|---|---|---|
| Valid credentials | 302 | → `LOGIN_REDIRECT_URL` (or `?next=` target) |
| Invalid credentials | 200 | form with `username` error, **no** "no such user" vs "wrong password" distinction |
| Inactive user (`is_active=False`) | 200 | same generic error, confirmed in `test_inactive_user_cannot_login` |
| Authenticated user opens login page | 302 | → `LOGIN_REDIRECT_URL`, no re-login |
| No `?next=` value | 302 | → `LOGIN_REDIRECT_URL` |
| `?next=` is an external host (`//evil.com`) | 302 | → `LOGIN_REDIRECT_URL` — open-redirect guard, Django's `url_has_allowed_host_and_scheme` |
| Logout via POST | 302 | → `LOGOUT_REDIRECT_URL`, session flushed |
| Logout via GET | 405 | `LogoutView` is POST-only in Django 5+ |

## Edge Cases

1. **`is_active=False` must not authenticate.** Covered by an explicit test, not assumed.
2. **`?next=` open redirect.** Django's `LoginView` already validates the host. We add a test to
   lock the behaviour in, because it is a security property.
3. **Double login.** `redirect_authenticated_user = True` sends an already-signed-in user to
   `LOGIN_REDIRECT_URL` instead of showing the form.
4. **Rate limiting / brute force.** Out of scope. SQLite deployment on a LAN per ARCHITECTURE.md
   §2. Flagged for later.
5. **SQLite write lock.** Login writes to `django_session`, so concurrent logins on a busy LAN can
   hit `database is locked`. Not specific to this feature; ARCHITECTURE.md §2 already accepts it.
   No retry logic added here.
6. **Sidebars need the session.** `base.html:26` gates the whole menu on `user.is_authenticated`.
   Without a login page this is always false. Fixing login makes the role sidebars testable.

## Known Pre-existing Bug (report only, not fixed here)

`base.html:46` reads `{% if user.role == 'CD' %}`. The stored role value is lowercase `"cd"`
(`accounts/models.py:6`), so the "ECs do Departamento" and "Histórico de Aprovações" links never
render. This affects the CD role, not the Administrator branch at line 60, which correctly compares
against `'administrator'`.

Fixing it belongs to the role-sidebar feature, not this one. Not touched here.

## Project Structure

```
apps/accounts/
├── urls.py             # new: login/ + logout/, app_name = "accounts"
├── views.py            # LoginView subclass + logout view
└── tests/
    └── test_views.py   # new tests
templates/accounts/
└── login.html          # new content (file already exists, currently empty)
config/
├── urls.py             # add include("apps.accounts.urls")
└── settings/base.py    # add LOGIN_URL / LOGIN_REDIRECT_URL / LOGOUT_REDIRECT_URL
```

## Code Style

Thin views, as ARCHITECTURE.md §6. Django's CBVs handle auth; we supply configuration only.

```python
# views.py
class TTLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
```

Line length 100, ruff-formatted.

## Testing Strategy

pytest-django + factory-boy, TDD: failing test first. Tests in
`apps/accounts/tests/test_views.py`, factories from the existing `UserFactory`.

1. `GET /accounts/login/` returns 200 and renders the form.
2. Valid credentials POST → 302 to `LOGIN_REDIRECT_URL`, session contains `_auth_user_id`.
3. Valid credentials with `?next=/backlog/ec/` → 302 to `/backlog/ec/`.
4. Invalid password → 200, error rendered, no session created.
5. Unknown username → 200, **identical** error message (no user enumeration).
6. `is_active=False` user → 200, cannot log in.
7. Authenticated user GETs login page → 302, redirected away.
8. `?next=https://evil.com/` → 302 to `LOGIN_REDIRECT_URL`, not to evil.com.
9. POST logout → 302, `_auth_user_id` gone from session.
10. GET logout → 405.

## Boundaries

- **Always:** TDD (red → green → refactor), `uv run pytest` + ruff before done, thin views, no
  secrets in code or templates.
- **Ask first:** new dependencies, any change to `accounts.User` or its migration, adding
  permissions/decorators to existing views, `is_active` semantics changes.
- **Never:** implement registration or password reset "while we're here", change
  `AUTH_USER_MODEL`, touch the `base.html` role bug, modify the `/admin/` login, commit
  `.env` or `db.sqlite3`.

## Success Criteria

- `/accounts/login/` renders a Portuguese Bootstrap form and successfully authenticates a real
  `accounts.User`.
- Session-based role sidebars in `base.html` become testable.
- Logout destroys the session.
- No open-redirect and no user enumeration, both locked in by tests.
- All new tests pass, full `uv run pytest` green, ruff clean.
- Zero migrations, zero changes to `accounts.User`.

## Open Questions

1. **Where does the login page live in the URL tree?** This spec uses `/accounts/login/`. The
   alternative is `/login/` at the root, which is shorter for users but couples the project URL to
   an app name. Recommend keeping `/accounts/` to match the app structure.
2. **Should inactive users see "contact the administrator" instead of the generic error?** A hint
   helps real staff but narrows user enumeration. Recommend generic error for now.

## Branch Name

`feature/accounts-login`