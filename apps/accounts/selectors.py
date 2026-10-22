from django.db.models import Q

from apps.accounts.models import User


def list_users(q=None):
    """Return every user ordered by username.

    `q` is the free-text search from the dashboard ("Pesquisar nome..."):
    it matches name, username or email, case-insensitively.
    """
    users = User.objects.all().order_by("username")
    if q:
        users = users.filter(
            Q(name__icontains=q) | Q(username__icontains=q) | Q(email__icontains=q)
        )
    return users
