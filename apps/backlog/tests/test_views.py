"""Release list page tests — spec `.opencode/specs/RELEASE_MODULE.md`.

Read `tests/test_models.py` first: same module-level `pytestmark`, same
`class Test...:` grouping style.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.backlog.tests.factories import ECFactory, ReleaseFactory

pytestmark = pytest.mark.django_db  # marka wainihra test ida access o sentuh database ka lae


class TestReleaseList:
    def test_returns_200(self, client):
        response = client.get(reverse("backlog:release_list"))
        assert response.status_code == 200

    def test_table_is_in_the_context(self, client):
        response = client.get(reverse("backlog:release_list"))
        assert "table" in response.context

    def test_shows_releases_from_the_database(self, client):
        release = ReleaseFactory(year=2027, number_sequence=99)
        response = client.get(reverse("backlog:release_list"))
        assert release.release_code in response.content.decode()

    def test_query_count_does_not_grow_with_rows(self, client):
        for _ in range(3):
            ReleaseFactory()
        with CaptureQueriesContext(connection) as small:
            client.get(reverse("backlog:release_list"))

        for _ in range(7):
            ReleaseFactory()

        with CaptureQueriesContext(connection) as large:
            client.get(reverse("backlog:release_list"))

        assert len(large) == len(small)

    def test_ratio_renders(self, client):
        release = ReleaseFactory(capacity=5)
        ECFactory(release=release)
        ECFactory(release=release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "2 / 5" in html

    def test_capacity_lotado(self, client):
        release = ReleaseFactory(capacity=2)
        ECFactory(release=release)
        ECFactory(release=release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "Lotado" in html

    def test_capacity_aberta(self, client):
        release = ReleaseFactory(capacity=3)
        ECFactory(release=release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "Aberta" in html

    def test_capacity_concluido(self, client):
        ReleaseFactory(capacity=3, is_open=False)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "Concluído" in html

    def test_closed_and_full_renders_lotado(self, client):
        release = ReleaseFactory(capacity=2, is_open=False)
        ECFactory(release=release)
        ECFactory(release=release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "Lotado" in html


class TestReleaseDetail:
    def test_returns_200_and_release_in_context(self, client):
        release = ReleaseFactory(year=2027, number_sequence=42)
        response = client.get(reverse("backlog:release_detail", args=[release.pk]))

        assert response.status_code == 200
        assert response.context["release"] == release

    def test_unknown_pk_returns_404(self, client):
        ReleaseFactory()
        response = client.get(reverse("backlog:release_detail", args=[99999]))

        assert response.status_code == 404

    def test_ocupancy(self, client):
        release = ReleaseFactory(capacity=3)
        ECFactory(release=release)
        ECFactory(release=release)
        response = client.get(reverse("backlog:release_detail", args=[release.pk]))
        html = response.content.decode()

        assert "2 / 3" in html

    def test_status_display(self, client):
        release = ReleaseFactory(capacity=2, is_open=False)
        ECFactory(release=release)
        ECFactory(release=release)
        response = client.get(reverse("backlog:release_detail", args=[release.pk]))
        html = response.content.decode()

        assert "Lotado" in html
