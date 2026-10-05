"""Release list page tests — spec `.opencode/specs/RELEASE_MODULE.md`.

Read `tests/test_models.py` first: same module-level `pytestmark`, same
`class Test...:` grouping style.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.backlog.models import Release
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

    def test_code_links_to_detail_and_no_action_column(self, client):
        release = ReleaseFactory()
        response = client.get(reverse("backlog:release_list"))
        table = response.context["table"]

        assert f'<a href="{reverse("backlog:release_detail", args=[release.pk])}"' in (
            response.content.decode()
        )
        assert "action" not in table.columns.names()


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

    def test_shows_only_this_releases_ecs(self, client):
        mine = ReleaseFactory()
        other = ReleaseFactory()
        my_ec = ECFactory(release=mine)
        other_ec = ECFactory(release=other)
        html = client.get(reverse("backlog:release_detail", args=[mine.pk])).content.decode()

        assert my_ec.reference in html
        assert other_ec.reference not in html

    def test_empty_release_renders_empty_state(self, client):
        release = ReleaseFactory()
        response = client.get(reverse("backlog:release_detail", args=[release.pk]))

        assert response.status_code == 200
        assert "Nenhuma EC encontrada." in response.content.decode()

    def test_query_count_does_not_grow_with_ecs(self, client):
        release = ReleaseFactory()
        for _ in range(3):
            ECFactory(release=release)
        with CaptureQueriesContext(connection) as small:
            client.get(reverse("backlog:release_detail", args=[release.pk]))

        for _ in range(7):
            ECFactory(release=release)

        with CaptureQueriesContext(connection) as large:
            client.get(reverse("backlog:release_detail", args=[release.pk]))

        assert len(large) == len(small)

    def test_page_param_shows_second_page_of_ecs(self, client):
        release = ReleaseFactory()
        ecs = [ECFactory(release=release) for _ in range(30)]

        url = reverse("backlog:release_detail", args=[release.pk])
        page1 = client.get(url).content.decode()
        page2 = client.get(url + "?page=2").content.decode()

        shown_on_p1 = [ec for ec in ecs if ec.reference in page1]
        shown_on_p2 = [ec for ec in ecs if ec.reference in page2]

        assert len(shown_on_p1) == 25
        assert len(shown_on_p2) == 5
        assert not set(shown_on_p1) & set(shown_on_p2)

    def test_dates_follow_spec_format(self, client):
        release = ReleaseFactory()
        Release.objects.filter(pk=release.pk).update(
            created_at=datetime(2026, 10, 5, 9, 30, tzinfo=ZoneInfo("Asia/Dili")),
            production_go_live_date=None,
        )
        html = client.get(reverse("backlog:release_detail", args=[release.pk])).content.decode()

        assert "05/10/2026 09:30" in html
        assert "Não definido" not in html
        assert "—" in html
