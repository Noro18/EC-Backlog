"""Dashboard tests — spec `.opencode/specs/DASHBOARD.md`.

Same module-level `pytestmark` and `class Test...:` grouping as `test_views.py`.
"""

from datetime import date

import pytest
from auditlog.context import set_actor
from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.backlog.models import EC
from apps.backlog.selectors import (
    admin_dashboard,
    dashboard_stats,
    des_team_dashboard,
    requester_dashboard,
)
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory
from apps.documents.models import DocumentVersion

pytestmark = pytest.mark.django_db

User = get_user_model()


def login_as(client, role):
    user = UserFactory(role=role)
    client.force_login(user)
    return user


class TestDashboardAccess:
    def test_requires_login(self, client):
        response = client.get(reverse("backlog:dashboard"))
        assert response.status_code == 302

    def test_returns_200_with_stats(self, client):
        login_as(client, User.Role.REQUESTER)
        response = client.get(reverse("backlog:dashboard"))

        assert response.status_code == 200
        assert "stats" in response.context


class TestRolePlaceholders:
    # Requester, CD, DES Team and Administrator rows are absent: their widgets
    # are implemented, so they show real content instead of a placeholder.

    def test_an_unknown_role_gets_no_placeholder(self, client):
        user = login_as(client, User.Role.REQUESTER)
        user.role = "not-a-role"
        user.save(update_fields=["role"])

        html = client.get(reverse("backlog:dashboard")).content.decode()

        assert "em construção" not in html

    def test_login_redirect_returns_to_the_dashboard(self, client):
        response = client.get(reverse("backlog:dashboard"))

        assert response.status_code == 302
        assert response.url == "/?next=/backlog/dashboard/"


class TestAdminDashboard:
    def test_admin_sees_header_kpis_users_and_activity(self, client):
        admin = UserFactory(role=User.Role.ADMINISTRATOR, name="Ana Admin")
        UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(status=EC.Status.IN_VALIDATION, requester=admin)
        ReleaseFactory(is_open=True)
        client.force_login(admin)

        response = client.get(reverse("backlog:dashboard"))
        html = response.content.decode()

        assert response.status_code == 200
        assert "admin" in response.context
        assert "log_table" in response.context
        assert "Painel do Administrador" in html
        assert "Ana Admin" in html
        assert "Utilizadores" in html
        assert "em curso" in html
        assert "aguardam revisão" in html
        assert "no registo de auditoria" in html
        assert "Atividade recente" in html
        assert "Ver todos os logs" in html
        assert "Pesquisar nome..." not in html
        # The feed is rendered by django-tables2 (`ActivityTable`), not a <ul>.
        assert "Hora" in html
        assert f"criou o EC {ec}" in html

    def test_non_admin_does_not_see_the_admin_panel(self, client):
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        html = client.get(reverse("backlog:dashboard")).content.decode()

        assert "Painel do Administrador" not in html
        assert "Atividade recente" not in html

    def test_the_user_list_stays_out_of_the_dashboard(self, client):
        # The list itself lives on `Gestão de Utilizadores` (accounts:user_list);
        # the dashboard only shows the KPI card and the activity chart.
        UserFactory(role=User.Role.REQUESTER, username="maria.costax")
        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR, username="boss.admin"))

        html = client.get(reverse("backlog:dashboard")).content.decode()

        assert "maria.costax@example.com" not in html
        assert "/admin/accounts/user/" not in html

    def test_counts_match_the_database(self):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        UserFactory(role=User.Role.CD)
        UserFactory(role=User.Role.DES_TEAM, is_active=False)
        open_release = ReleaseFactory(is_open=True)
        ReleaseFactory(is_open=False)
        # Both ECs share the open release so they do not create extra releases.
        ECFactory(status=EC.Status.IN_VALIDATION, requester=admin, release=open_release)
        ECFactory(status=EC.Status.CLOSED, requester=admin, release=open_release)

        data = admin_dashboard(admin)

        assert data["users_total"] == 3
        assert data["users_active"] == 2
        assert data["releases_total"] == 2
        assert data["releases_open"] == 1
        assert data["ec_total"] == 2
        assert data["ec_pending_review"] == 1

    def test_recent_logs_come_from_auditlog(self):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(requester=admin)  # save() writes a LogEntry row

        data = admin_dashboard(admin)

        assert data["actions_today"] >= 1
        assert data["recent_logs"]
        entry = data["recent_logs"][0]
        assert f"criou o EC {ec}" in entry["description"]
        assert len(entry["time"]) == 5  # "HH:MM"

    def test_an_upload_reads_as_one_portuguese_sentence(self):
        admin = UserFactory(role=User.Role.ADMINISTRATOR, name="Maria da Costa")
        ec = ECFactory(requester=admin)
        # The actor comes from the request (auditlog middleware); `set_actor`
        # is how auditlog exposes that outside of a real request.
        with set_actor(admin):
            DocumentVersion.objects.create(
                ec=ec, version_number="v1.0", uploaded_by=admin
            )

        data = admin_dashboard(admin)

        assert any(
            "Maria da Costa" in log["description"]
            and "enviou a v1.0" in log["description"]
            and ec.ec_code in log["description"]
            for log in data["recent_logs"]
        )

    def test_the_feed_is_limited_to_the_five_latest_entries(self):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        for _ in range(7):
            ECFactory(requester=admin)

        data = admin_dashboard(admin)

        assert len(data["recent_logs"]) == 5

    def test_empty_feed_shows_the_portuguese_placeholder(self, client):
        # ADMIN_DASHBOARD.md edge case 1: a fresh install has nothing to show
        # and must not render a blank card.
        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR))
        LogEntry.objects.all().delete()

        html = client.get(reverse("backlog:dashboard")).content.decode()

        assert "Sem atividade registada." in html

    def test_log_without_an_actor_reads_as_sistema(self):
        # ADMIN_DASHBOARD.md edge case 2: rows written outside a request carry
        # `actor=None`, which must read as a name, never as "None".
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ECFactory(requester=admin)

        descriptions = [log["description"] for log in admin_dashboard(admin)["recent_logs"]]

        assert descriptions
        assert any(text.startswith("Sistema") for text in descriptions)
        assert all("None" not in text for text in descriptions)


class TestDashboardStats:
    def test_status_counts_include_zero_for_missing_statuses(self):
        counts = dashboard_stats(UserFactory())["ec_by_status"]

        assert set(counts) == {value for value, _label in EC.Status.choices}
        assert not any(counts.values())  # nothing exists yet -> all zeros
        assert counts[EC.Status.IN_VALIDATION] == 0

    def test_release_occupancy_matches_ec_count(self):
        release = ReleaseFactory(capacity=5)
        ECFactory(release=release)
        ECFactory(release=release)

        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        rows = dashboard_stats(admin)["releases"]

        assert rows[0]["ec_count"] == 2
        assert rows[0]["percent"] == 40

    def test_zero_capacity_never_divides_by_zero(self):
        ReleaseFactory(capacity=0)

        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        assert dashboard_stats(admin)["releases"][0]["percent"] == 0

    def test_monthly_series_uses_creation_date(self):
        user = UserFactory()
        ECFactory(requester=user, creation_date=date(2026, 8, 2))
        ECFactory(requester=user, creation_date=date(2026, 8, 17))
        ECFactory(requester=user, creation_date=date(2026, 9, 1))
        ECFactory(requester=user, creation_date=None)  # historical import

        months = dashboard_stats(user)["ec_by_month"]

        assert months == [
            {"month": "2026-08", "count": 2},
            {"month": "2026-09", "count": 1},
        ]

    def test_requester_only_counts_their_own_ecs(self):
        mine = UserFactory(role=User.Role.REQUESTER)
        ECFactory(requester=mine)
        ECFactory(requester=UserFactory(role=User.Role.REQUESTER))

        assert dashboard_stats(mine)["ec_total"] == 1

    def test_requester_sees_no_release_capacity(self):
        ReleaseFactory()
        ReleaseFactory()

        stats = dashboard_stats(UserFactory(role=User.Role.REQUESTER))

        assert stats["releases"] == []
        assert stats["releases_open"] == 0


class TestRequesterDashboard:
    """Widgets that do not need a CD decision yet (draft / submitted).

    Decisions live in `workflow.Review`, and `apps/backlog` must not import
    `workflow` (ARCHITECTURE §5) — those cases are covered by
    `apps/workflow/tests/test_dashboard_decisions.py`.
    """

    @staticmethod
    def _upload(ec, version):
        # `ec.versions` is the reverse manager of DocumentVersion, so we can
        # create a version without importing `apps.documents`.
        return ec.versions.create(
            version_number=version,
            file="documents/spec.pdf",
            uploaded_by=ec.requester,
        )

    def test_ec_without_a_document_counts_as_in_validation(self):
        user = UserFactory(role=User.Role.REQUESTER)
        ECFactory(requester=user)

        assert requester_dashboard(user)["by_status"]["in_validation"] == 1

    def test_my_ecs_lists_each_ec_with_reference_and_status(self):
        user = UserFactory(role=User.Role.REQUESTER)
        ECFactory(requester=user, reference="COR2026001")
        ECFactory(requester=user, reference="COR2026002")

        my_ecs = requester_dashboard(user)["my_ecs"]

        assert [row["reference"] for row in my_ecs] == ["COR2026002", "COR2026001"]
        assert all(row["status"] == EC.Status.IN_VALIDATION for row in my_ecs)
        assert all(row["versions_count"] == 0 for row in my_ecs)
        assert all(row["versions"] == [] for row in my_ecs)

    def test_my_ecs_counts_uploaded_versions(self):
        user = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=user, reference="COR2026003")
        self._upload(ec, "v1")
        self._upload(ec, "v2")

        my_ecs = requester_dashboard(user)["my_ecs"]

        assert len(my_ecs) == 1
        assert my_ecs[0]["id"] == ec.id
        assert my_ecs[0]["reference"] == "COR2026003"
        assert my_ecs[0]["status"] == EC.Status.IN_VALIDATION
        assert my_ecs[0]["versions_count"] == 2
        assert my_ecs[0]["versions"] == ["v1", "v2"]

    def test_my_ecs_excludes_other_requesters(self):
        mine = UserFactory(role=User.Role.REQUESTER)
        ECFactory(requester=mine, reference="COR2026004")
        ECFactory(requester=UserFactory(role=User.Role.REQUESTER), reference="COR2026005")

        my_ecs = requester_dashboard(mine)["my_ecs"]

        assert [row["reference"] for row in my_ecs] == ["COR2026004"]

    def test_uploaded_but_undecided_counts_as_in_validation(self):
        user = UserFactory(role=User.Role.REQUESTER)
        self._upload(ECFactory(requester=user), "v1")

        stats = requester_dashboard(user)

        assert stats["by_status"]["in_validation"] == 1
        assert stats["versions_total"] == 1

    def test_versions_per_document_counts_every_upload(self):
        user = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=user, reference="CR2026903")
        self._upload(ec, "v1")
        self._upload(ec, "v2")
        self._upload(ec, "v3")

        assert requester_dashboard(user)["versions_per_document"] == [
            {"reference": "CR2026903", "versions": 3}
        ]

    def test_requester_only_sees_their_own_documents(self):
        mine = UserFactory(role=User.Role.REQUESTER)
        other = UserFactory(role=User.Role.REQUESTER)
        self._upload(ECFactory(requester=mine), "v1")
        self._upload(ECFactory(requester=other), "v1")

        assert requester_dashboard(mine)["ec_total"] == 1

    def test_recent_uploads_are_sorted_newest_first(self):
        user = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=user, reference="CR2026901")
        self._upload(ec, "v1")
        self._upload(ec, "v2")

        recent = requester_dashboard(user)["recent_versions"]

        assert [row["version"] for row in recent] == ["v2", "v1"]

    def test_page_renders_the_requester_widgets(self, client):
        user = UserFactory(role=User.Role.REQUESTER)
        ECFactory(requester=user)
        client.force_login(user)

        response = client.get(reverse("backlog:dashboard"))
        html = response.content.decode()

        assert response.status_code == 200
        assert "req" in response.context
        assert "Documentos por estado" in html
        # The rejections card was deliberately removed from the dashboard.
        assert "precisam da sua ação" not in html
        # The placeholder must be gone once the real widgets are in place.
        assert "em construção" not in html


class TestDesTeamDashboard:
    def test_des_team_dashboard_lists_routed_ecs(self):
        des_user = UserFactory(role=User.Role.DES_TEAM)
        ECFactory(status=EC.Status.CLOSED, reference="DES2026001")

        data = des_team_dashboard(des_user)

        assert data["sent_total"] == 1
        assert data["sent_ecs"][0].reference == "DES2026001"

    def test_page_renders_des_team_widgets(self, client):
        user = UserFactory(role=User.Role.DES_TEAM)
        ECFactory(status=EC.Status.CLOSED, reference="DES2026002")
        client.force_login(user)

        response = client.get(reverse("backlog:dashboard"))
        html = response.content.decode()

        assert response.status_code == 200
        assert "des" in response.context
        assert "DES2026002" in html
        assert "em construção" not in html

