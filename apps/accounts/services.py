from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .forms import ProfileUpdateForm, UserCreateForm, UserUpdateForm
from .models import User


def create_user(form: UserCreateForm) -> User:
    """USER_CREATE.md Decision 5: validation in the form, saving here.

    RNF02: the auditlog signal registered in admin.py records the actor and
    the time — no LogEntry row is written by hand.
    """
    return form.save()  # UserCreationForm hashes password1 before saving


def update_user(form: UserUpdateForm) -> User:
    """Update an existing user via ModelForm."""
    return form.save()


def deactivate_user(user: User, acting_user: User) -> None:
    """Deactivate a user, preventing self-deactivation."""
    if user.pk == acting_user.pk:
        raise ValidationError("Não pode desativar a sua própria conta.")
    user.is_active = False
    user.save(update_fields=["is_active"])


def update_profile(form: ProfileUpdateForm) -> User:
    """PROFILE_SELF_EDIT.md: validation in the form, saving here.

    Only `name` and `email` can change (RNF01: users edit their own data);
    auditlog records the edit automatically — no LogEntry row by hand.
    """
    return form.save()


def change_password(form: PasswordChangeForm, request: HttpRequest) -> User:
    """Hash and persist the new password, keeping the session alive.

    PasswordChangeForm has already verified the current password and run
    AUTH_PASSWORD_VALIDATORS; update_session_auth_hash re-marks the session
    so the user is not logged out by their own change.
    """
    user = form.save()
    update_session_auth_hash(request, user)
    return user

