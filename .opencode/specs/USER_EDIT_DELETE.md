# Spec — Edit and Delete/Deactivate Users (issue #68)

## Objective

`GET|POST /accounts/users/<pk>/editar/` and `POST /accounts/users/<pk>/apagar/` let an Administrator
manage existing users directly from `Gestão de Utilizadores`, without leaving the app for `/admin/`.

- As an Administrator, I click *Editar* on any user in the table, update their `name`, `email`,
  `role`, or active status (`is_active`), and save.
- As an Administrator, I click *Apagar* (or *Desativar*) on a user, and the system deactivates or
  removes them safely without crashing on foreign-key protection constraints.
- As an Administrator, I am returned to the user list with a success message.
- As a non-administrator (Requester, CD, DES Team), I get **403** on all edit/delete endpoints.

**Why this exists — SRD mapping.** SRD §4 ("System Administrator: Manages users, access profiles..."),
RNF01 (distinct profiles), RNF02 (auditing via auditlog). Issue #68 completes the user CRUD cycle
alongside PR #73 (`user_create`).

**Out of scope:** Password reset from the UI, editing `username`, self-registration, bulk actions,
forcing a user logout.

## Assumptions

1. The Administrator role is checked via `UserPassesTestMixin` (`role == "administrator"`), matching
   `UserListView` and `UserCreateView`.
2. `username` is **immutable** after creation — changing it invalidates logs and references.
3. Because `EC.requester`, `EC.responsible_cd`, `DocumentVersion.uploaded_by`, and `Review.cd` use
   `on_delete=models.PROTECT`, hard-deleting a user who has ever created an EC, uploaded a document,
   or approved/rejected a review will trigger a database `ProtectedError`.
   **Decision:** The "Apagar" action will **deactivate** the user (`is_active = False`) rather than
   performing a hard delete, avoiding SQL crashes while fulfilling the removal requirement. If a hard
   delete is attempted on an unused user, it succeeds; if protected, it deactivates and reports the
   reason via a success/warning message.
4. An Administrator cannot deactivate or delete **their own account** while logged in (self-lockout
   guard).
5. Baseline on this branch: **270 tests green**.

## Decisions (proposed)

1. **Editable fields on `UserUpdateForm`**: `name`, `email`, `role`, `is_active`. `username` and
   password are excluded.
2. **Form class**: `UserUpdateForm(forms.ModelForm)` in `apps/accounts/forms.py`, using the same
   Portuguese labels and Bootstrap widgets as `UserCreateForm`.
3. **Service layer**: `update_user(user, form)` and `deactivate_user(user)` in
   `apps/accounts/services.py`.
4. **Delete/Deactivate view**: A POST-only view (`UserDeleteView`) that calls `deactivate_user` and
   redirects back to the list with a message.
5. **Table update**: `UserTable.render_edit` points to `accounts:user_update` (`/accounts/users/<pk>/editar/`),
   and a new column or action adds the delete/deactivate button (or inline link).
6. **Audit log (RNF02)**: `auditlog.register(User)` is already active (`apps/accounts/admin.py:35`),
   so `.save()` and `.delete()` (or field updates) automatically record the acting administrator.

## Tech Stack

Django 6.1 class-based views (`UpdateView`, `View`), `django-tables2`, Bootstrap 5.
**No new dependencies**.

## Commands

```bash
uv run pytest apps/accounts/tests/ -q
uv run pytest -q                       # 270 -> ~278
uv run ruff check .
uv run python manage.py runserver
```

## System Architecture

```
apps/accounts/
├── forms.py        # + UserUpdateForm(ModelForm)
├── services.py     # + update_user(user, form), deactivate_user(user)
├── views.py        # + UserUpdateView, UserDeleteView
├── urls.py         # + users/<pk>/editar/, users/<pk>/apagar/
├── tables.py       # + render_edit (repointed), render_delete/actions
└── tests/          # + test_forms.py (rename from test_form.py if needed), test_views.py
templates/accounts/
├── user_form.html  # shared or user_edit.html (reuse with title check)
└── user_list.html  # table with working Edit / Delete buttons
```

Import direction: `accounts` imports no other app.

## Database Schema Changes

**None.** Uses existing `is_active` boolean and `User` model.

## Input / Output

**GET** `/accounts/users/<pk>/editar/` → 200 with pre-filled form for Administrator; 403 for others.
**POST** `/accounts/users/<pk>/editar/` → 302 to `accounts:user_list` on success with success message.
**POST** `/accounts/users/<pk>/apagar/` → 302 to `accounts:user_list`, deactivates user, shows message.

## Edge Cases

1. **Admin deactivates themselves** → refused with `ValidationError` / message ("Não pode desativar a sua própria conta").
2. **Deleting a user with ECs** → handled gracefully via deactivation (or protected caught).
3. **Email already taken by another user** → form validation error.

## Testing Strategy

TDD: failing test first.
New tests in `apps/accounts/tests/`:
1. Admin gets pre-filled edit form.
2. Admin updates name/role successfully.
3. Non-admin gets 403 on edit and delete.
4. Admin deactivates a user successfully.
5. Admin cannot deactivate themselves.
6. Audit log records user update and deactivation (RNF02).

Expected suite: **270 + 6 = 276**.

## Success Criteria

- [ ] *Editar* button on `Gestão de Utilizadores` opens the edit form pre-filled.
- [ ] Saving updates the user and writes an auditlog row.
- [ ] Deactivate/delete button deactivates the user safely without crashing on PROTECT foreign keys.
- [ ] Admin cannot deactivate their own account.
- [ ] Non-administrators get 403.
- [ ] 276 tests green, `ruff check .` clean.

## Branch Name

`feat/user-edit-delete`
