"""Model tests for `accounts.User` (spec `database-scheme.md` 4.2)."""

import pytest

from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestFullName:
    """`full_name` is the display source; `first_name`/`last_name` stay untouched."""

    def test_full_name_prefers_the_name_field(self):
        user = UserFactory(name="Jane Doe", first_name="Janet")

        assert user.full_name == "Jane Doe"

    def test_full_name_falls_back_to_first_and_last_name(self):
        user = UserFactory(name="", first_name="Jane", last_name="Doe")

        assert user.full_name == "Jane Doe"

    def test_save_does_not_sync_name_into_first_name(self):
        user = UserFactory(name="Jane Doe", first_name="", last_name="")
        user.save()

        assert user.first_name == ""
        assert user.last_name == ""
