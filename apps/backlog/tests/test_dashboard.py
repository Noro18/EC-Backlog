"""Dashboard tests — spec `.opencode/specs/DASHBOARD.md`.

Same module-level `pytestmark` and `class Test...:` grouping as `test_views.py`.
"""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.backlog.models import EC
from apps.backlog.selectors import dashboard_stats, requester_dashboard
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory

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
    # The requester row is deliberately absent: its widgets are implemented,
    # so it shows real content instead of a placeholder (see
    # `TestRequesterDashboard` below).
    @pytest.mark.parametrize(
        "role,expected",
        [
            (User.Role.CD, "Widgets específicos do CD"),
            (User.Role.DES_TEAM, "Widgets específicos do DES Team"),
            (User.Role.ADMINISTRATOR, "Widgets específicos do Administrador"),
        ],
    )
    def test_the_dashboard_shows_the_placeholder_of_the_signed_in_role(
        self, client, role, expected
    ):
        login_as(client, role)
        html = client.get(reverse("backlog:dashboard")).content.decode()

        assert expected in html

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
        assert "precisam da sua ação" in html
        # The placeholder must be gone once the real widgets are in place.
        assert "em construção" not in html
