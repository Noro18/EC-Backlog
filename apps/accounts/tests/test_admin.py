import pytest
from auditlog.models import LogEntry
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import identify_hasher

pytestmark = pytest.mark.django_db

User = get_user_model()

ADD_URL = "/admin/accounts/user/add/"

PAYLOAD = {
    "username": "barucoba",
    "email": "baru@example.com",
    "name": "Baru Coba",
    "role": "cd",
    "first_name": "",
    "last_name": "",
    "password1": "SenhaForte123!",
    "password2": "SenhaForte123!",
    "is_active": "on",
    "is_staff": "on",
}


class TestAdminUserCreate:
    def test_add_form_creates_the_user_with_its_role(self, admin_client):
        assert admin_client.post(ADD_URL, PAYLOAD).status_code == 302

        assert User.objects.filter(username="barucoba", role="cd").exists()

    def test_password_is_stored_hashed_and_can_log_in(self, admin_client):
        admin_client.post(ADD_URL, PAYLOAD)

        user = User.objects.get(username="barucoba")

        identify_hasher(user.password)  # raises ValueError if the value is plaintext
        assert user.password != "SenhaForte123!"
        assert authenticate(username="barucoba", password="SenhaForte123!") == user


class TestAdminUserAudit:
    def test_user_changes_reach_the_audit_log(self, admin_client, admin_user):
        # RNF02 / ADMIN_DASHBOARD.md: `auditlog.register(User)` lives in
        # apps/accounts/admin.py, so a change made here must feed the dashboard.
        admin_client.post(ADD_URL, PAYLOAD)

        user = User.objects.get(username="barucoba")
        entry = LogEntry.objects.get(
            content_type__model="user", object_pk=str(user.pk)
        )

        assert entry.action == LogEntry.Action.CREATE
        assert entry.actor == admin_user  # who
        assert entry.timestamp is not None  # and when