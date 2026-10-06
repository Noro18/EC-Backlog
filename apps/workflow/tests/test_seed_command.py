"""Tests for the `seed_dashboard_demo` management command.

The command is the only way to see the requester widgets with real content,
so it is worth pinning down: it must produce exactly the scenario the
dashboard was designed around, and it must refuse to touch a production DB.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.backlog.selectors import requester_dashboard
from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestSeedDashboardDemo:
    # Django's test environment forces DEBUG=False, which is exactly what the
    # command's safety guard looks for — so opt in explicitly for the tests
    # that are supposed to succeed.
    @override_settings(DEBUG=True)
    def test_produces_the_expected_requester_scenario(self):
        call_command("seed_dashboard_demo")

        requester = UserFactory(username="demo_req", role="requester")
        stats = requester_dashboard(requester)

        assert stats["by_status"] == {
            "in_validation": 4,
            "approved": 2,
            "rejected": 1,
            "sent_to_des": 0,
            "closed": 0,
        }
        assert stats["ec_total"] == 7
        assert stats["versions_total"] == 9

        # The bar chart must have a clear winner: one EC revised three times.
        counts = [row["versions"] for row in stats["versions_per_document"]]
        assert counts[:2] == [3, 2]

        # Exactly one rejection is still waiting for the requester to act.
        assert len(stats["needs_action"]) == 1
        assert stats["needs_action"][0]["comment"] == "Falta a justificação do impacto."

    @override_settings(DEBUG=True)
    def test_creates_all_four_demo_roles(self):
        call_command("seed_dashboard_demo")

        roles = set(
            get_user_model()
            .objects.filter(username__startswith="demo_")
            .values_list("role", flat=True)
        )

        assert roles == {"requester", "cd", "des_team", "administrator"}

    @override_settings(DEBUG=False)
    def test_refuses_to_run_outside_debug(self):
        with pytest.raises(CommandError):
            call_command("seed_dashboard_demo")
