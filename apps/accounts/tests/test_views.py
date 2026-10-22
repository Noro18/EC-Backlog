"""User list page tests — spec `.opencode/specs/ACCOUNTS_USER_LIST.md`.

Same module-level `pytestmark` and `class Test...:` style as
`apps/backlog/tests/test_views.py`.
"""

import pytest
from django.urls import reverse

from apps.accounts.tables import ROLE_BADGE_CLASSES
from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestUserList:
    def test_administrator_gets_200(self, client):
        client.force_login(UserFactory(role="administrator"))

        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 200

    def test_shows_every_user(self, client):
        client.force_login(UserFactory(role="administrator"))
        for username in ["alice", "bruno", "carla", "diego", "elisa", "fabio"]:
            UserFactory(username=username)

        html = client.get(reverse("accounts:user_list")).content.decode()

        assert all(name in html for name in ["alice", "bruno", "carla", "diego", "elisa", "fabio"])

    def test_empty_name_falls_back_to_username(self, client):
        client.force_login(UserFactory(role="administrator"))
        UserFactory(username="semnome", name="", first_name="", last_name="")

        html = client.get(reverse("accounts:user_list")).content.decode()

        # without the fallback the username shows once (Utilizador column);
        # with it, twice (Nome + Utilizador)
        assert html.count("semnome") >= 2

    def test_last_login_null_shows_placeholder(self, client):
        client.force_login(UserFactory(role="administrator"))
        UserFactory(username="nuncaentrou", last_login=None)

        html = client.get(reverse("accounts:user_list")).content.decode()

        assert "—" in html
        assert "nuncaentrou" in html

    def test_each_role_maps_to_its_badge(self, client):
        client.force_login(UserFactory(role="administrator"))
        for role in ROLE_BADGE_CLASSES:
            UserFactory(username=f"u_{role}", role=role)

        html = client.get(reverse("accounts:user_list")).content.decode()

        assert all(css in html for css in ROLE_BADGE_CLASSES.values())

    def test_pagination_second_page(self, client):
        client.force_login(UserFactory(role="administrator"))
        for n in range(30):
            UserFactory(username=f"pag{n:02d}", role="requester")

        first = client.get(reverse("accounts:user_list"))
        second = client.get(reverse("accounts:user_list") + "?page=2")

        assert second.status_code == 200
        # pagination lives in django-tables2, not in MultipleObjectMixin
        assert second.context["table"].page.number == 2
        assert "pag00" in first.content.decode()
        assert "pag00" not in second.content.decode()

    def test_search_filters_the_table(self, client):
        client.force_login(UserFactory(role="administrator"))
        UserFactory(username="maria.costax")
        UserFactory(username="joao.soares")

        html = client.get(reverse("accounts:user_list"), {"q": "maria.costax"}).content.decode()

        assert "maria.costax@example.com" in html
        assert "joao.soares@example.com" not in html

    def test_edit_column_links_to_the_admin_change_form(self, client):
        client.force_login(UserFactory(role="administrator"))
        target = UserFactory(username="para.editar")

        html = client.get(reverse("accounts:user_list")).content.decode()

        assert f'/admin/accounts/user/{target.pk}/change/' in html
        assert "Editar" in html

    def test_non_administrator_gets_403(self, client):
        # ACCOUNTS_USER_LIST.md: permission is enforced in the view, and the
        # gap carried since scope A is now closed — the page gained actions.
        client.force_login(UserFactory(role="requester"))

        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 403
