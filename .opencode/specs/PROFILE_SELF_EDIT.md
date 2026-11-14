# Spec — Self-Service Profile (`Meu Perfil`)

**Status:** SPEC_DRAFT — waiting for `SPEC_APPROVED` before any implementation code.

## Objective

Give every authenticated user — of any role — one page to manage their own personal
data: edit their **name** and **email**, and change their **password** with the
current password as proof of ownership. The **username** and **role** are read-only
on this page; username changes are an Administrator task (the page shows a note
saying so).

This fills the profile icon placeholder (`href="#"`) in the top navbar
(`templates/components/navbar.html`), giving it a real target. It also completes the
sidebar cleanup the owner already shipped (commit `e872550` on this branch): the
`Relatórios` and `Configurações` `#` menu entries are commented out, so the navbar
profile icon is the single remaining account entry point.

**Scope note (honest record):** the SRD RF list has no requirement for a self-service
profile. The project owner added this scope deliberately. It relates to RNF01 (users
may only touch their own data) and RNF02 (the django-auditlog registration on
`accounts.User` records every edit automatically). It is not tied to the still-open
SRD § 4 question about a dedicated Administrator profile.

## Tech Stack

Django 6.1 built-ins only: a `ModelForm`, Django's `PasswordChangeForm`, and
`update_session_auth_hash`. Bootstrap 5 components as in every other page.
**No new Python dependency, no CDN, no new model.**

## Commands

```bash
uv run pytest apps/accounts/tests/test_profile.py  # feature tests
uv run pytest                                      # full suite
uv run ruff check .                                # lint
uv run python manage.py runserver                  # manual check, any role
```

## System Architecture

```
apps/accounts/
├── forms.py      # ADD ProfileUpdateForm (fields: name, email; username/role excluded)
│                 # Portuguese labels + Bootstrap widgets, same style as the admin forms
├── services.py   # ADD update_profile(form) and change_password(form, request)
│                 # single write points; the view stays thin
├── views.py      # ADD ProfileView: LoginRequiredMixin only (no role test);
│                 # two forms, two POST kinds (form=pessoa | form=senha)
├── urls.py       # ADD /accounts/profile/ (route name: accounts:profile)
└── tests/
    └── test_profile.py  # NEW (TDD red first, ~14 tests)

templates/accounts/profile.html   # NEW: two cards, Portuguese labels
templates/components/navbar.html  # EDIT: profile icon href="#" → {% url 'accounts:profile' %}
```

Convention check against `docs/ARCHITECTURE.md`: validation lives in the form, the
write lives in the service, the view only orchestrates. `models.py`, `admin.py`,
`tables.py`, and selectors are untouched — auditlog already tracks `accounts.User`
changes, so no manual log entry and no migration is needed.

## Database Schema Changes

**None.** The page edits existing `accounts.User` fields (`name`, `email`,
`password`); everything else about the model stays as is.

## Page Definition

**URL:** `/accounts/profile/` (route `accounts:profile`), title **Meu Perfil**.

**Card 1 — Dados pessoais:**

- Editable: `Nome` (required, same contract as the admin forms), `Email`
  (required, unique enforced).
- Read-only display: `Nome de utilizador` and `Perfil`
  (`{{ user.get_role_display }}`).
- Note under the username: username changes go through the Administrator.
- Save button: `Guardar alterações`; on success a Portuguese flash message
  (`Dados atualizados com sucesso.`).

**Card 2 — Alterar palavra-passe:**

- Fields: `Palavra-passe atual`, `Nova palavra-passe`, `Confirmar nova
  palavra-passe` — Django's `PasswordChangeForm` (validators from
  `AUTH_PASSWORD_VALIDATORS`, matching the admin-created users' rules).
- On success: `Palavra-passe alterada com sucesso.` and the session survives the
  change (`update_session_auth_hash`) — the user is never logged out by their own
  password change.

**Navbar:** the person icon (currently `href="#"`) links to `accounts:profile`.

**Portuguese UI strings**, English code/commits — same convention as every feature.

## Input / Output

| Request | Result |
|---|---|
| GET `/accounts/profile/` (anonymous) | 302 redirect to `LOGIN_URL` |
| GET `/accounts/profile/` (any logged-in role) | 200, both cards |
| POST `form=pessoa` (name, email) | saves name/email; invalid → field errors (PT) |
| POST `form=senha` (current_password, password1, password2) | hashes new password; invalid → field errors (PT) |

**Hard limits (security):** `role`, `is_active`, and `username` are never writable
by this page; the password change always requires the current password (a hijacked
session cannot lock out the real owner).

## Edge Cases

1. Duplicate email → form error `Este email já está em uso.` (unique=True).
2. Wrong current password → `PasswordChangeForm` field error, no change happens.
3. Weak or mismatched new password → validator / confirmation errors (PT).
4. Blank `Nome` → required-field error, same contract as the admin forms.
5. Auditlog keeps recording every change (actor + timestamp, RNF02) — nothing to add.

## Acceptance Criteria

1. Any logged-in role (requester, CD, des_team, administrator) reaches the page;
   anonymous users are redirected to login.
2. Name + email edits persist and appear immediately in the navbar identity line.
3. Username and role are displayed read-only and cannot be changed through this page
   (no writable field, no update path in the service).
4. Password change requires the correct current password, applies
   `AUTH_PASSWORD_VALIDATORS`, keeps the session alive, and the new password works
   on the next login while the old one stops working.
5. The navbar person icon opens the page.
6. Duplicate email, wrong current password, weak password, and blank name each show
   a clear Portuguese error and change nothing.
7. **Done:** feature tests + full suite pass; `uv run ruff check .` clean;
   `manage.py check` and `makemigrations --check` clean; no migration; no new
   dependency.

## Approved Decisions

1. **Password:** user-changeable on this page; the current password is required.
2. **Username:** read-only, with an "via Administrator" note (owner decision,
   recorded in conversation 2026-11-10).
3. **Email:** self-editable; uniqueness enforced with a Portuguese error.
4. **Placement:** navbar person icon → `accounts:profile`; no sidebar menu is added.
5. **Labels:** `Meu Perfil`, `Dados pessoais`, `Alterar palavra-passe`.
6. **Scope:** owner-approved addition beyond the RF list; the still-open SRD § 4
   Administrator-profile question is not resolved by this spec.

## Open Decisions (blocking spec approval)

None — awaiting only the owner's `SPEC_APPROVED`.
