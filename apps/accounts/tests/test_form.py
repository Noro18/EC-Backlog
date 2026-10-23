"""User creation form tests — spec `.opencode/specs/USER_CREATE.md`."""

import pytest

from apps.accounts.forms import UserCreateForm
from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

VALID = {
    "username": "maria.gusmao",
    "name": "Maria Gusmao",
    "email": "maria@example.com",
    "role": "cd",
    "is_active": True,
    "password1": "SenhaForte123!",
    "password2": "SenhaForte123!",
}


def form_with(**overrides):
    """VALID with a few keys replaced — a None value means the key is dropped."""
    data = {**VALID, **overrides}
    data = {k: v for k, v in data.items() if v is not None}
    return UserCreateForm(data=data)


class TestUserCreateForm:
    def test_a_complete_form_is_valid(self):
        assert form_with().is_valid()

    def test_mismatched_passwords_are_rejected(self):
        form = form_with(password2="OutraSenha456!")

        assert not form.is_valid()
        assert "password2" in form.errors

    def test_passwords_shorter_than_eight_characters_are_rejected(self):
        form = form_with(password1="curta", password2="curta")

        assert not form.is_valid()
        # Decision 8: assert on the field key, never on Django's English text
        assert "password2" in form.errors

    def test_a_duplicate_username_is_rejected(self):
        UserFactory(username="ja.existe")
        form = form_with(username="ja.existe")

        assert not form.is_valid()
        assert "username" in form.errors

    def test_a_duplicate_email_is_rejected(self):
        UserFactory(email="ja@example.com")
        form = form_with(email="ja@example.com")

        assert not form.is_valid()
        assert "email" in form.errors

    def test_the_profile_is_required(self):
        form = form_with(role=None)          # key dropped from the data

        assert not form.is_valid()
        assert "role" in form.errors

    def test_the_name_is_required(self):
        form = form_with(name="")            # Decision 7

        assert not form.is_valid()
        assert "name" in form.errors