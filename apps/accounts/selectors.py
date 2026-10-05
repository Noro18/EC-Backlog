from apps.accounts.models import User


def list_users():
    """Return every user, ordered by username."""
    return User.objects.all().order_by("username")