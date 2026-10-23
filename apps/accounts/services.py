from .forms import UserCreateForm
from .models import User


def create_user(form: UserCreateForm) -> User:
    """USER_CREATE.md Decision 5: validation in the form, saving here.

    RNF02: the auditlog signal registered in admin.py records the actor and
    the time — no LogEntry row is written by hand.
    """
    return form.save()  # UserCreationForm hashes password1 before saving