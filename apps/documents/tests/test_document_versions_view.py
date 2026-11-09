import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory

pytestmark = pytest.mark.django_db


def add_version(ec, number, change_reason=""):
    return DocumentVersionFactory(
        ec=ec,
        uploaded_by=ec.requester,
        version_number=number,
        change_reason=change_reason,
    )


def page_url():
    return reverse("documents:document_versions")


class TestDocumentVersionsAccess:
    def test_administrator_can_view_the_page(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        client.force_login(admin)

        response = client.get(page_url())

        assert response.status_code == 200
        assert "Versões de Documentos" in response.content.decode()

    @pytest.mark.parametrize("role", ["requester", "cd", "des_team"])
    def test_non_administrators_get_forbidden(self, client, role):
        user = UserFactory(role=role)
        client.force_login(user)

        assert client.get(page_url()).status_code == 403

    def test_anonymous_redirects_to_login(self, client):
        response = client.get(page_url())

        assert response.status_code == 302
        assert "?next=" in response.url


class TestDocumentVersionsPage:
    def test_every_version_is_listed_newest_first(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        older = add_version(ec, "v1.0", change_reason="first upload")
        newer = add_version(ec, "v1.1", change_reason="fixed diagram")

        client.force_login(admin)
        html = client.get(page_url()).content.decode()

        assert html.index("fixed diagram") < html.index("first upload")
        assert reverse("backlog:ec_detail", args=[ec.pk]) in html
        assert reverse("documents:download", args=[newer.pk]) in html
        assert reverse("documents:download", args=[older.pk]) in html
        assert reverse("documents:preview", args=[newer.pk]) in html
        assert reverse("documents:preview", args=[older.pk]) in html

    def test_versions_from_other_ecs_are_listed_too(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        first = ECFactory(release=None)
        second = ECFactory(release=None)
        add_version(first, "v1.0", change_reason="first ec upload")
        DocumentVersionFactory(
            ec=second,
            uploaded_by=second.requester,
            version_number="v1.0",
            change_reason="second ec upload",
        )

        client.force_login(admin)
        html = client.get(page_url()).content.decode()

        assert "first ec upload" in html
        assert "second ec upload" in html

    def test_search_by_ec_reference_filters_the_rows(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        match = ECFactory(release=None, reference="CR2026SP")
        other = ECFactory(release=None)
        add_version(match, "v1.0", change_reason="matching row")
        add_version(other, "v1.0", change_reason="other row")

        client.force_login(admin)
        html = client.get(page_url(), {"q": "CR2026SP"}).content.decode()

        assert "matching row" in html
        assert "other row" not in html

    def test_search_without_match_shows_the_empty_state(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")

        client.force_login(admin)
        html = client.get(page_url(), {"q": "no-such-key"}).content.decode()

        assert "Ainda sem documentos." in html

    def test_rows_are_paginated_by_25(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        for _ in range(26):
            ec = ECFactory(release=None)
            add_version(ec, "v1.0")

        client.force_login(admin)
        response = client.get(page_url())
        html = response.content.decode()

        assert html.count("data-version-row=") == 25
        assert "?page=2" in html
