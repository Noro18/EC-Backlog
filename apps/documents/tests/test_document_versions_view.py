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


def list_url():
    return reverse("documents:document_versions")


def gallery_url(ec):
    return reverse("documents:ec_versions", args=[ec.pk])


def upload_url(version):
    return reverse("documents:download", args=[version.pk])


def preview_url(version):
    return reverse("documents:preview", args=[version.pk])


class TestDocumentVersionsAccess:
    def test_administrator_can_view_the_chip_list(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        client.force_login(admin)

        response = client.get(list_url())

        assert response.status_code == 200
        assert "Versões de Documentos" in response.content.decode()

    def test_administrator_can_view_the_ec_gallery(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")
        client.force_login(admin)

        response = client.get(gallery_url(ec))

        assert response.status_code == 200
        assert "Ver EC completa" in response.content.decode()

    @pytest.mark.parametrize("role", ["requester", "cd", "des_team"])
    @pytest.mark.parametrize("page", ["list", "gallery"])
    def test_non_administrators_get_forbidden(self, client, role, page):
        user = UserFactory(role=role)
        ec = ECFactory(release=None, requester=user)
        add_version(ec, "v1.0")

        client.force_login(user)
        url = list_url() if page == "list" else gallery_url(ec)

        assert client.get(url).status_code == 403

    def test_anonymous_redirects_to_login(self, client):
        response = client.get(list_url())

        assert response.status_code == 302
        assert "?next=" in response.url

    def test_anonymous_gallery_redirects_to_login(self, client):
        ec = ECFactory(release=None)

        response = client.get(gallery_url(ec))

        assert response.status_code == 302
        assert "?next=" in response.url


class TestDocumentChips:
    def test_each_ec_with_versions_renders_one_chip(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        first = ECFactory(release=None, reference="CR2026SP")
        second = ECFactory(release=None)
        add_version(first, "v1.0", change_reason="first ec upload")
        add_version(second, "v1.0", change_reason="second ec upload")

        client.force_login(admin)
        html = client.get(list_url()).content.decode()

        assert html.count("data-ec-chip=") == 2
        assert "2 versões" not in html
        assert reverse("documents:ec_versions", args=[first.pk]) in html
        assert reverse("documents:ec_versions", args=[second.pk]) in html
        assert "CR2026SP" in html
        assert "first ec upload" not in html  # chips, not the old row table

    def test_chip_shows_the_version_count(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")
        add_version(ec, "v1.1")

        client.force_login(admin)
        html = client.get(list_url()).content.decode()

        assert "2 versões" in html

    def test_ecs_are_ordered_by_their_newest_upload(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        older = ECFactory(release=None)
        newer = ECFactory(release=None)
        add_version(older, "v1.0")
        add_version(newer, "v1.0")

        client.force_login(admin)
        html = client.get(list_url()).content.decode()

        assert html.index(newer.ec_code) < html.index(older.ec_code)

    def test_ec_without_versions_renders_no_chip(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        with_docs = ECFactory(release=None)
        without_docs = ECFactory(release=None)
        add_version(with_docs, "v1.0")

        client.force_login(admin)
        html = client.get(list_url()).content.decode()

        assert reverse("documents:ec_versions", args=[with_docs.pk]) in html
        assert reverse("documents:ec_versions", args=[without_docs.pk]) not in html

    def test_search_by_ec_code_filters_the_chips(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        match = ECFactory(release=None)
        other = ECFactory(release=None)
        add_version(match, "v1.0")
        add_version(other, "v1.0")

        client.force_login(admin)
        html = client.get(list_url(), {"q": f"EC-{match.ec_code}"}).content.decode()

        assert "data-ec-chip=" in html
        assert reverse("documents:ec_versions", args=[match.pk]) in html
        assert reverse("documents:ec_versions", args=[other.pk]) not in html

    def test_search_by_ec_reference_filters_the_chips(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        match = ECFactory(release=None, reference="CR2026SP")
        other = ECFactory(release=None)
        add_version(match, "v1.0", change_reason="matching row")
        add_version(other, "v1.0", change_reason="other row")

        client.force_login(admin)
        html = client.get(list_url(), {"q": "CR2026SP"}).content.decode()

        assert "matching row" not in html  # chips carry no change reasons
        assert "data-ec-chip=" in html
        assert reverse("documents:ec_versions", args=[other.pk]) not in html

    def test_search_without_match_shows_the_empty_state(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")

        client.force_login(admin)
        html = client.get(list_url(), {"q": "no-such-key"}).content.decode()

        assert "Ainda sem documentos." in html
        assert "data-ec-chip=" not in html


class TestECGallery:
    def test_versions_are_listed_newest_first(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        older = add_version(ec, "v1.0", change_reason="first upload")
        newer = add_version(ec, "v1.1", change_reason="fixed diagram")

        client.force_login(admin)
        html = client.get(gallery_url(ec)).content.decode()

        assert html.index("fixed diagram") < html.index("first upload")
        assert html.count("data-version-card=") == 2
        assert preview_url(newer) in html
        assert preview_url(older) in html
        assert upload_url(newer) in html
        assert upload_url(older) in html

    def test_cards_carry_the_thumbnail_marker(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")
        add_version(ec, "v1.1")

        client.force_login(admin)
        html = client.get(gallery_url(ec)).content.decode()

        assert html.count("data-thumbnail-url=") == 2

    def test_gallery_links_back_and_to_the_ec_detail(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        add_version(ec, "v1.0")

        client.force_login(admin)
        html = client.get(gallery_url(ec)).content.decode()

        assert list_url() in html  # Voltar link
        assert reverse("backlog:ec_detail", args=[ec.pk]) in html

    def test_version_without_file_renders_without_actions(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        DocumentVersionFactory(ec=ec, version_number="v1.0", file="")

        client.force_login(admin)
        html = client.get(gallery_url(ec)).content.decode()

        assert "data-version-card=" in html
        assert "data-thumbnail-url=" not in html
        assert "Descarregar" not in html

    def test_gallery_for_ec_without_versions_returns_404(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(release=None)
        client.force_login(admin)

        assert client.get(gallery_url(ec)).status_code == 404

    def test_gallery_for_unknown_ec_returns_404(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        client.force_login(admin)

        assert client.get("/documents/document-versions/999999/").status_code == 404
