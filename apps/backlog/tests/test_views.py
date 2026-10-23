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
from apps.backlog.services import NEW_RELEASE
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory
from apps.documents.models import DocumentVersion

pytestmark = pytest.mark.django_db  # marka wainihra test ida access o sentuh database ka lae


def docx_file(name="spec.docx"):
    """A minimal valid .docx payload — every EC-create POST needs one now."""
    return SimpleUploadedFile(
        name,
        b"dummy content",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


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

    def test_closed_and_full_renders_concluido(self, client):
        release = ReleaseFactory(capacity=2, is_open=False)
        ECFactory(release=release)
        ECFactory(release=release)
        html = client.get(reverse("backlog:release_list")).content.decode()

        assert "Concluído" in html

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


class TestECListVisibility:
    """RF01 / access control — each role sees only its own ECs."""

    @staticmethod
    def _login(client, role):
        user = UserFactory(role=role)
        client.force_login(user)
        return user

    def test_requester_sees_only_their_own_ecs(self, client):
        mine_user = self._login(client, User.Role.REQUESTER)
        other_user = UserFactory(role=User.Role.REQUESTER)
        mine = ECFactory(requester=mine_user)
        theirs = ECFactory(requester=other_user)

        page = client.get(reverse("backlog:ec_list")).content.decode()

        assert mine.reference in page
        assert theirs.reference not in page

    def test_cd_sees_only_ecs_assigned_to_them(self, client):
        me = self._login(client, User.Role.CD)
        mine = ECFactory(responsible_cd=me)
        someone_else = ECFactory(responsible_cd=UserFactory(role=User.Role.CD))

        page = client.get(reverse("backlog:ec_list")).content.decode()

        assert mine.reference in page
        assert someone_else.reference not in page

    def test_administrator_sees_every_ec(self, client):
        self._login(client, User.Role.ADMINISTRATOR)
        first = ECFactory()
        second = ECFactory()

        page = client.get(reverse("backlog:ec_list")).content.decode()

        assert first.reference in page
        assert second.reference in page

    def test_des_team_only_sees_closed_ecs(self, client):
        self._login(client, User.Role.DES_TEAM)
        closed = ECFactory(status=EC.Status.CLOSED)
        still_validating = ECFactory(status=EC.Status.IN_VALIDATION)

        page = client.get(reverse("backlog:ec_list")).content.decode()

        assert closed.reference in page
        assert still_validating.reference not in page

    def test_anonymous_users_are_redirected_to_login(self, client):
        response = client.get(reverse("backlog:ec_list"))

        assert response.status_code == 302


class TestECListSearch:
    """RF12 — the toolbar above the EC list filters by text and status."""

    @staticmethod
    def _login(client, role=User.Role.ADMINISTRATOR):
        user = UserFactory(role=role)
        client.force_login(user)
        return user

    def test_q_filters_by_reference(self, client):
        self._login(client)
        hit = ECFactory(reference="COR2026001")
        miss = ECFactory(reference="XYZ9999999")

        page = client.get(reverse("backlog:ec_list"), {"q": "COR2026"}).content.decode()

        assert hit.reference in page
        assert miss.reference not in page

    def test_q_filters_by_description(self, client):
        self._login(client)
        hit = ECFactory(description="Troca do módulo de billing")
        miss = ECFactory(description="Ajuste de layout")

        page = client.get(reverse("backlog:ec_list"), {"q": "billing"}).content.decode()

        assert hit.reference in page
        assert miss.reference not in page

    def test_q_matches_the_ec_id(self, client):
        self._login(client)
        hit = ECFactory(year=2019, number_sequence=12, reference="OLD2019")
        miss = ECFactory(year=2026, number_sequence=12, reference="NEW2026")

        page = client.get(reverse("backlog:ec_list"), {"q": "2019-012"}).content.decode()

        assert hit.reference in page
        assert miss.reference not in page

    def test_q_matches_the_ec_id_with_the_displayed_prefix(self, client):
        """The table renders 'EC-2019-012', so users type it that way too."""
        self._login(client)
        hit = ECFactory(year=2019, number_sequence=12, reference="OLD2019")
        miss = ECFactory(year=2026, number_sequence=12, reference="NEW2026")

        page = client.get(reverse("backlog:ec_list"), {"q": "EC-2019-012"}).content.decode()

        assert hit.reference in page
        assert miss.reference not in page

    def test_status_select_filters_the_table(self, client):
        self._login(client)
        approved = ECFactory(status=EC.Status.APPROVED)
        rejected = ECFactory(status=EC.Status.REJECTED)

        page = client.get(reverse("backlog:ec_list"), {"status": "approved"}).content.decode()

        assert approved.reference in page
        assert rejected.reference not in page

    def test_text_and_status_filters_combine(self, client):
        self._login(client)
        wanted = ECFactory(reference="BETA-001", status=EC.Status.APPROVED)
        wrong_status = ECFactory(reference="BETA-002", status=EC.Status.REJECTED)
        wrong_text = ECFactory(reference="ALFA-001", status=EC.Status.APPROVED)

        page = client.get(
            reverse("backlog:ec_list"), {"q": "BETA", "status": "approved"}
        ).content.decode()

        assert wanted.reference in page
        assert wrong_status.reference not in page
        assert wrong_text.reference not in page


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

        assert "Concluído" in html
        assert '<span class="badge text-bg-secondary">Concluído</span>' in html

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
                "document": docx_file("adm.docx"),
            },
        )
        assert response.status_code == 302
        assert EC.objects.filter(reference="CR-ADM-001").exists()

    def test_sidebar_shows_link_for_requester_only(self, client):
        # The sidebar "Nova Solicitação" link belongs to the requester
        # section only; admins create ECs through the button on ec_list.
        client.force_login(UserFactory(role=User.Role.REQUESTER))
        response_requester = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") in response_requester.content.decode()

        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR))
        response_admin = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") not in response_admin.content.decode()

        client.force_login(UserFactory(role=User.Role.CD))
        response_cd = client.get(reverse("backlog:release_list"))
        assert reverse("backlog:ec_form") not in response_cd.content.decode()

    def test_admin_sees_new_ec_button_on_ec_list(self, client):
        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR))
        response = client.get(reverse("backlog:ec_list"))
        assert reverse("backlog:ec_form") in response.content.decode()


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
                "document": docx_file(),
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

    def test_post_without_document_is_rejected(self, client):
        """EC_CREATE_DOCUMENT_REQUIRED.md test 1: no file → no EC at all."""
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        self._login_requester(client)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026042",
                "description": "Trocar o resistor R12",
                "release": release.pk,
                "responsible_cd": cd.pk,
            },
        )
        assert response.status_code == 200
        assert "document" in response.context["form"].errors
        assert EC.objects.count() == 0
        assert DocumentVersion.objects.count() == 0

    def test_failed_attempt_consumes_no_ec_number(self, client):
        """EC_CREATE_DOCUMENT_REQUIRED.md test 2: the first success is still -001."""
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        self._login_requester(client)
        payload = {
            "reference": "CR2026042",
            "description": "Trocar o resistor R12",
            "release": release.pk,
            "responsible_cd": cd.pk,
        }

        client.post(reverse("backlog:ec_form"), data=payload)  # no document → rejected

        payload["document"] = docx_file()
        response = client.post(reverse("backlog:ec_form"), data=payload)
        assert response.status_code == 302
        assert EC.objects.get().ec_code == f"{timezone.localdate().year}-001"

    def test_document_field_is_required_on_get(self, client):
        """EC_CREATE_DOCUMENT_REQUIRED.md test 3: required flag + * marker in the label."""
        self._login_requester(client)
        response = client.get(reverse("backlog:ec_form"))
        assert response.context["form"].fields["document"].required is True
        assert (
            'Carregar Documento (.docx / .pdf) <span class="text-danger">*</span>'
            in response.content.decode()
        )

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
                "document": docx_file(),
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
                "document": docx_file(),
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
                "document": docx_file(f"spec{i}.docx"),
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

        docx = docx_file("test.docx")

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


class TestReleaseOnDemand:
    """RELEASE_CREATE_ON_DEMAND.md (RF02): '+ Kria Release Foun' in the dropdown."""

    @staticmethod
    def _login_requester(client):
        client.force_login(UserFactory(role=User.Role.REQUESTER))

    def test_dropdown_lists_new_option_last(self, client):
        year = timezone.localdate().year
        release = ReleaseFactory(year=year, number_sequence=1)
        self._login_requester(client)

        html = client.get(reverse("backlog:ec_form")).content.decode()

        assert f'value="{NEW_RELEASE}"' in html
        assert "+ Kria Release Foun" in html
        assert html.index(release.release_code) < html.index(NEW_RELEASE)

    def test_new_option_creates_next_release(self, client):
        year = timezone.localdate().year
        old = ReleaseFactory(year=year, number_sequence=3)
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026042",
                "description": "Precisa release foun",
                "release": NEW_RELEASE,
                "responsible_cd": cd.pk,
                "document": docx_file(),
            },
        )

        assert response.status_code == 302
        ec = EC.objects.get()
        assert ec.release.release_code == f"TT_ON_{year}-004"
        assert old.ecs.count() == 0

    def test_new_option_despite_room_in_old_releases(self, client):
        year = timezone.localdate().year
        roomy = ReleaseFactory(year=year, number_sequence=1)
        ECFactory(release=roomy, year=year, number_sequence=1)
        ECFactory(release=roomy, year=year, number_sequence=2)
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026043",
                "description": "Hakarak foun maski tuan mamuk",
                "release": NEW_RELEASE,
                "responsible_cd": cd.pk,
                "document": docx_file(),
            },
        )

        assert response.status_code == 302
        ec = EC.objects.latest("id")
        assert ec.release.release_code == f"TT_ON_{year}-002"
        assert roomy.ecs.count() == 2

    def test_new_release_appears_in_dropdown_afterwards(self, client):
        year = timezone.localdate().year
        ReleaseFactory(year=year, number_sequence=3)
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026045",
                "description": "Depois haree iha dropdown",
                "release": NEW_RELEASE,
                "responsible_cd": cd.pk,
                "document": docx_file(),
            },
        )
        assert response.status_code == 302

        html = client.get(reverse("backlog:ec_form")).content.decode()
        assert f"TT_ON_{year}-004 (aberta" in html

    def test_garbage_release_is_rejected(self, client):
        ReleaseFactory()
        self._login_requester(client)
        count_before = Release.objects.count()

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "CR2026044",
                "description": "Release falsu",
                "release": "999999",
                "responsible_cd": UserFactory(role=User.Role.CD).pk,
                "document": docx_file(),
            },
        )

        assert response.status_code == 200
        assert response.context["form"].errors
        assert EC.objects.count() == 0
        assert Release.objects.count() == count_before


class TestReferencePrefixSuggestions:
    """Single reference input + CR/RT/COR suggestions on click (RNF05)."""

    @staticmethod
    def _login_requester(client):
        client.force_login(UserFactory(role=User.Role.REQUESTER))

    def test_get_renders_single_input_with_prefix_suggestions(self, client):
        self._login_requester(client)
        html = client.get(reverse("backlog:ec_form")).content.decode()
        assert 'name="reference"' in html
        assert 'name="reference_prefix"' not in html
        assert 'name="reference_number"' not in html
        for prefix in ("CR", "RT", "COR"):
            assert f'data-prefix="{prefix}"' in html

    def test_post_full_reference_creates_ec(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_form"),
            data={
                "reference": "RT2026042",
                "description": "Trocar o resistor R12",
                "release": release.pk,
                "responsible_cd": cd.pk,
                "document": docx_file(),
            },
        )
        assert response.status_code == 302
        assert EC.objects.get().reference == "RT2026042"


def _upload(ec, version, change_reason=""):
    """Attach a document version through the reverse manager (no documents import)."""
    return ec.versions.create(
        version_number=version,
        file="documents/spec.pdf",
        uploaded_by=ec.requester,
        change_reason=change_reason,
    )


class TestECDetail:
    def test_requires_login(self, client):
        ec = ECFactory()
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_returns_200_and_ec_in_context(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        assert response.status_code == 200
        assert response.context["ec"] == ec

    def test_unknown_pk_returns_404(self, client):
        client.force_login(UserFactory())
        response = client.get(reverse("backlog:ec_detail", args=[99999]))

        assert response.status_code == 404

    def test_shows_real_data(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        html = client.get(reverse("backlog:ec_detail", args=[ec.pk])).content.decode()

        assert f"EC-{ec.ec_code}" in html
        assert ec.reference in html
        assert ec.description in html
        assert ec.requester.full_name in html
        assert ec.release.release_code in html

    def test_status_badge_class(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(ec.requester)
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        assert response.context["status_badge_class"] == "text-bg-warning"
        assert '<span class="badge text-bg-warning">' in response.content.decode()

    def test_no_versions_renders_empty_state(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        assert response.context["ec"] == ec
        assert "Ainda sem documentos" in response.content.decode()

    def test_shows_uploaded_version(self, client):
        ec = ECFactory()
        _upload(ec, "v1.0")
        client.force_login(ec.requester)
        html = client.get(reverse("backlog:ec_detail", args=[ec.pk])).content.decode()

        assert "v1.0" in html
        assert "enviado por" in html

    def test_timeline_creation_event_first(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        timeline = response.context["timeline"]

        first = timeline[0]
        assert first["title"] == "EC criada"
        assert first["who"] == ec.requester.full_name
        assert first["when"] == ec.created_at
        assert first["note"] is None

    def test_timeline_upload_events_oldest_first(self, client):
        ec = ECFactory()
        _upload(ec, "v1.0", change_reason="Primeira submissão")
        _upload(ec, "v1.1")
        client.force_login(ec.requester)
        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        timeline = response.context["timeline"]

        assert [event["title"] for event in timeline] == [
            "EC criada",
            "Documento v1.0 carregado",
            "Documento v1.1 carregado",
        ]
        assert timeline[1]["note"] == "Primeira submissão"
        assert timeline[2]["note"] is None
        whens = [event["when"] for event in timeline]
        assert whens == sorted(whens)

    def test_creation_date_format(self, client):
        ec = ECFactory()
        EC.objects.filter(pk=ec.pk).update(
            created_at=datetime(2026, 10, 5, 9, 30, tzinfo=ZoneInfo("Asia/Dili"))
        )
        client.force_login(ec.requester)
        html = client.get(reverse("backlog:ec_detail", args=[ec.pk])).content.decode()

        assert "Criada em 05/10/2026 às 09:30" in html

    def test_query_count_does_not_grow_with_versions(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        for i in range(3):
            _upload(ec, f"v1.{i}")

        with CaptureQueriesContext(connection) as small:
            first = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        for i in range(3, 7):
            _upload(ec, f"v1.{i}")

        with CaptureQueriesContext(connection) as large:
            second = client.get(reverse("backlog:ec_detail", args=[ec.pk]))

        assert first.context["ec"] == ec
        assert second.context["ec"] == ec
        assert len(large) == len(small)


class TestECEditView:
    """EC_EDIT.md (issue #67): edit the content of an in-flight EC."""

    def _data(self, ec, **overrides):
        data = {
            "reference": ec.reference,
            "description": ec.description,
            "release": ec.release.pk,
            "responsible_cd": ec.responsible_cd_id or UserFactory(role=User.Role.CD).pk,
        }
        data.update(overrides)
        return data

    def test_requires_login(self, client):
        ec = ECFactory()
        response = client.get(reverse("backlog:ec_edit", args=[ec.pk]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_owner_gets_a_prefilled_form(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(ec.requester)

        response = client.get(reverse("backlog:ec_edit", args=[ec.pk]))

        assert response.status_code == 200
        form = response.context["form"]
        assert form["reference"].value() == ec.reference
        assert form["description"].value() == ec.description
        assert int(form["release"].value()) == ec.release_id

    def test_form_exposes_only_the_editable_fields(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(ec.requester)

        form = client.get(reverse("backlog:ec_edit", args=[ec.pk])).context["form"]

        assert list(form.fields) == [
            "reference",
            "description",
            "release",
            "responsible_cd",
        ]
        assert form.fields["release"].required is True

    def test_owner_saves_and_returns_to_the_detail_page(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(ec.requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, reference="CR2026555", description="Texto revisto"),
            follow=True,
        )

        assert response.redirect_chain[-1][0] == reverse("backlog:ec_detail", args=[ec.pk])
        assert "atualizada" in response.content.decode()
        ec.refresh_from_db()
        assert ec.reference == "CR2026555"
        assert ec.description == "Texto revisto"

    def test_non_owner_gets_403(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        response = client.get(reverse("backlog:ec_edit", args=[ec.pk]))

        assert response.status_code == 403

    def test_cd_gets_403(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        client.force_login(UserFactory(role=User.Role.CD))

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]), data=self._data(ec)
        )

        assert response.status_code == 403

    def test_administrator_can_edit_an_imported_ec(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION, requester=None, is_imported=True)
        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR))

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, reference="CR2026444"),
        )

        assert response.status_code == 302
        ec.refresh_from_db()
        assert ec.reference == "CR2026444"

    def test_approved_ec_is_refused(self, client):
        ec = ECFactory(status=EC.Status.APPROVED)
        client.force_login(ec.requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, reference="CR2026333"),
        )

        assert response.status_code == 403
        ec.refresh_from_db()
        assert ec.reference != "CR2026333"

    def test_identity_and_status_cannot_be_smuggled_in(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION, year=2026, number_sequence=7)
        client.force_login(ec.requester)

        client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(
                ec,
                year=1999,
                number_sequence=99,
                status=EC.Status.CLOSED,
                creation_date="1999-01-01",
                implemented_at="1999-01-01T00:00",
                is_imported="true",
            ),
        )

        ec.refresh_from_db()
        assert (ec.year, ec.number_sequence) == (2026, 7)
        assert ec.status == EC.Status.IN_VALIDATION
        assert ec.creation_date != "1999-01-01"
        assert ec.is_imported is False

    def test_full_target_release_is_refused(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        target = ReleaseFactory(year=2027, number_sequence=5, capacity=1)
        ECFactory(release=target, year=2027, number_sequence=1)
        client.force_login(ec.requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, release=target.pk),
        )

        assert response.status_code == 200
        assert response.context["form"].errors
        ec.refresh_from_db()
        assert ec.release != target

    def test_keeping_a_full_current_release_works(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        release = ReleaseFactory(capacity=1)
        ec = ECFactory(requester=requester, release=release, status=EC.Status.IN_VALIDATION)
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, description="Só a descrição"),
        )

        assert response.status_code == 302
        ec.refresh_from_db()
        assert ec.description == "Só a descrição"

    def test_detail_shows_the_edit_button_only_for_the_owner(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)

        client.force_login(ec.requester)
        owner_html = client.get(reverse("backlog:ec_detail", args=[ec.pk])).content.decode()
        assert reverse("backlog:ec_edit", args=[ec.pk]) in owner_html
        assert "Editar" in owner_html

        client.force_login(UserFactory(role=User.Role.REQUESTER))
        other = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        assert other.status_code == 200
        assert other.context["can_edit"] is False
        assert "Editar" not in other.content.decode()

    def test_owner_changes_the_responsible_cd(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        old_cd = UserFactory(role=User.Role.CD)
        new_cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(
            requester=requester, responsible_cd=old_cd, status=EC.Status.IN_VALIDATION
        )
        client.force_login(requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, responsible_cd=new_cd.pk),
        )

        assert response.status_code == 302
        ec.refresh_from_db()
        assert ec.responsible_cd == new_cd

    def test_a_non_cd_responsible_is_refused(self, client):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        intruder = UserFactory(role=User.Role.REQUESTER)
        client.force_login(ec.requester)

        response = client.post(
            reverse("backlog:ec_edit", args=[ec.pk]),
            data=self._data(ec, responsible_cd=intruder.pk),
        )

        assert response.status_code == 200
        assert "responsible_cd" in response.context["form"].errors
        ec.refresh_from_db()
        assert ec.responsible_cd_id != intruder.pk
