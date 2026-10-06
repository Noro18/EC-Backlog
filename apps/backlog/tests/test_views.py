"""Release list page tests — spec `.opencode/specs/RELEASE_MODULE.md`.

Read `tests/test_models.py` first: same module-level `pytestmark`, same
`class Test...:` grouping style.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC, Release
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory
from apps.documents.models import DocumentVersion

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

    def test_badge_palette_matches_spec(self, client):
        open_release = ReleaseFactory(capacity=3)
        ECFactory(release=open_release)
        ReleaseFactory(capacity=3, is_open=False)
        full_release = ReleaseFactory(capacity=1)
        ECFactory(release=full_release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert '<span class="badge text-bg-success">Aberta</span>' in html
        assert '<span class="badge text-bg-secondary">Concluído</span>' in html
        assert '<span class="badge text-bg-danger">Lotado</span>' in html

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
        assert '<span class="badge text-bg-danger">Lotado</span>' in html

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


class TestNewECRoleGate:
    """EC_CREATE.md tests 7-9, 11: hiding the link is not the permission check."""

    def test_anonymous_user_get_redirected_to_login(self, client):
        response = client.get(reverse("backlog:ec_form"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    @pytest.mark.parametrize("role", [User.Role.CD, User.Role.DES_TEAM])
    def test_cd_get_forbidden(self, client, role):
        cd_user = UserFactory(role=role)
        client.force_login(cd_user)
        response = client.get(reverse("backlog:ec_form"))

        assert response.status_code == 403

    def test_cd_post_forbidden(self, client):
        cd_user = UserFactory(role=User.Role.CD)
        client.force_login(cd_user)
        response = client.post(reverse("backlog:ec_form"), data={})

        assert response.status_code == 403
        assert EC.objects.count() == 0

    def test_administrator_gets_and_creates(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(admin)

        assert client.get(reverse("backlog:ec_form")).status_code == 200

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR-ADM-001",
                "description": "Administrador também pode criar",
                "release": release.pk,
                "responsible_cd": cd.pk,
            },
        )
        assert response.status_code == 302
        assert EC.objects.filter(reference="CR-ADM-001").exists()

    def test_sidebar_shows_link_for_requester_admin_not_cd(self, client):
        requester_user = UserFactory(role=User.Role.REQUESTER)
        admin_user = UserFactory(role=User.Role.ADMINISTRATOR)
        client.force_login(requester_user)
        response_requester = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") in response_requester.content.decode()

        client.force_login(admin_user)
        response_admin = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") in response_admin.content.decode()

        client.force_login(UserFactory(role=User.Role.CD))
        response_cd = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") not in response_cd.content.decode()


class TestNewECForm:
    """EC_CREATE.md tests 12, 13, 15, 17, 18, 20 — the ECCreateForm slice (M5)."""

    @staticmethod
    def _login_requester(client):
        client.force_login(UserFactory(role=User.Role.REQUESTER))

    def test_get_renders_form_in_context(self, client):
        self._login_requester(client)
        response = client.get(reverse("backlog:ec_form"))
        assert response.status_code == 200
        assert "form" in response.context

    def test_valid_post_creates_ec_and_renders_message(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026042",
                "description": "Trocar o resistor R12",
                "release": release.pk,
                "responsible_cd": cd.pk,
            },
        )
        assert response.status_code == 302
        assert response.url == reverse("backlog:ec_list")

        ec = EC.objects.get()
        assert ec.ec_code == f"{timezone.localdate().year}-001"
        assert ec.requester == requester
        assert ec.creation_date == timezone.localdate()

        page = client.get(reverse("backlog:ec_list")).content.decode()
        assert "criada com sucesso" in page

    def test_blank_description_is_rejected(self, client):
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        self._login_requester(client)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026999",
                "description": "",
                "release": release.pk,
                "responsible_cd": cd.pk,
            },
        )
        assert response.status_code == 200
        assert response.context["form"].errors
        assert EC.objects.count() == 0

    def test_post_to_full_release_is_refused(self, client):
        cd = UserFactory(role=User.Role.CD)
        full = ReleaseFactory(capacity=1)
        ECFactory(release=full)
        self._login_requester(client)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026111",
                "description": "Não cabe",
                "release": full.pk,
                "responsible_cd": cd.pk,
            },
        )
        assert response.status_code == 200
        assert EC.objects.count() == 1  # only the pre-existing EC, nothing created

    def test_two_consecutive_posts_increment_the_number(self, client):
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        self._login_requester(client)

        payloads = [
            {
                "reference": f"CR202600{i}",
                "description": f"solicitação {i}",
                "release": release.pk,
                "responsible_cd": cd.pk,
            }
            for i in range(1, 3)
        ]
        codes = []
        for payload in payloads:
            response = client.post(reverse("backlog:ec_form"), data=payload)
            assert response.status_code == 302
            codes.append(EC.objects.latest("id").ec_code)

        year = timezone.localdate().year
        assert codes == [f"{year}-001", f"{year}-002"]

    def test_dropdown_excludes_closed_and_full_releases(self, client):
        open_ok = ReleaseFactory()
        full = ReleaseFactory(capacity=1)
        ECFactory(release=full)
        closed = ReleaseFactory(is_open=False)
        self._login_requester(client)

        form = client.get(reverse("backlog:ec_form")).context["form"]
        queryset = form.fields["release"].queryset

        assert open_ok in queryset
        assert full not in queryset
        assert closed not in queryset

    def test_dropdown_query_count_does_not_grow_with_releases(self, client):
        """Spec test 19: constant queries as releases grow — kills a raw-loop N+1.

        Fails if open_releases_with_ec_count() is swapped for per-option counting.
        """
        self._login_requester(client)
        client.get(reverse("backlog:ec_form"))  # warm-up: session/auth queries paid once

        for _ in range(3):
            ReleaseFactory()
        with CaptureQueriesContext(connection) as small:
            client.get(reverse("backlog:ec_form"))

        for _ in range(7):
            ReleaseFactory()
        with CaptureQueriesContext(connection) as large:
            client.get(reverse("backlog:ec_form"))

        assert len(large) == len(small)

    def test_upload_creates_first_document_version(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(requester)

        docx = SimpleUploadedFile(
            "test.docx",
            b"dummy content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026042",
                "description": "Trocar o resistor R12",
                "release": release.pk,
                "responsible_cd": cd.pk,
                "document": docx,
            },
        )
        assert response.status_code == 302
        ec = EC.objects.get()
        version = DocumentVersion.objects.get(ec=ec)
        assert version.version_number == "v1.0"
        assert version.uploaded_by == requester
        assert version.ec == ec

    def test_exe_upload_is_rejected(self, client):
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        self._login_requester(client)

        virus = SimpleUploadedFile(
            "test.exe", b"dummy content", content_type="application/x-msdownload"
        )

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026042",
                "description": "Trocar o resistor R12",
                "release": release.pk,
                "responsible_cd": cd.pk,
                "document": virus,
            },
        )
        assert response.status_code == 200  # re render orm with error
        assert "document" in response.context["form"].errors
        assert DocumentVersion.objects.count() == 0
        assert EC.objects.count() == 0
