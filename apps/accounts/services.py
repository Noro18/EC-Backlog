from django.core.exceptions import ValidationError

from .forms import UserCreateForm, UserUpdateForm
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