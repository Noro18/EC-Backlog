import pytest
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