"""Requester dashboard widgets that depend on a CD decision.

These tests need `workflow.Review`, so they cannot live in
`apps/backlog/tests/` — ARCHITECTURE §5 forbids `backlog` from importing
`workflow`, and that rule covers test modules too. `workflow` sits at the
top of the arrow chain, so it may read everything below it.

Since issue #96 the dashboard reads `EC.status` directly (the services keep
it in sync), so the state is driven here through the real `workflow`
services instead of raw `ReviewFactory` rows.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.selectors import requester_dashboard
from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.workflow.models import Review
from apps.workflow.services import approve_ec, reject_ec, resubmit_ec, route_to_des
from apps.workflow.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db


def _upload(ec, version):
    """Attach a document version through the reverse manager (no documents import)."""
    return ec.versions.create(
        version_number=version, file="documents/spec.pdf", uploaded_by=ec.requester
    )


def _ec_with_cd(user, **ec_kwargs):
    cd = UserFactory(role=User.Role.CD)
    return ECFactory(requester=user, responsible_cd=cd, **ec_kwargs)


class TestRequesterDecisions:
    def test_approval_on_the_latest_version_counts_as_approved(self):
        user = UserFactory(role="requester")
        ec = _ec_with_cd(user)
        _upload(ec, "v1")

        approve_ec(ec, ec.responsible_cd)

        assert requester_dashboard(user)["by_status"]["approved"] == 1

    def test_rejection_lands_in_needs_action_with_the_comment(self):
        user = UserFactory(role="requester")
        ec = _ec_with_cd(user)
        _upload(ec, "v1")

        reject_ec(ec, ec.responsible_cd, "Falta a justificação do impacto.")

        stats = requester_dashboard(user)

        assert stats["by_status"]["rejected"] == 1
        assert stats["needs_action"][0]["reference"] == ec.reference
        assert stats["needs_action"][0]["comment"] == "Falta a justificação do impacto."
        # The EC id drives the link to the detail page in the template.
        assert stats["needs_action"][0]["id"] == ec.id

    def test_a_new_upload_after_a_rejection_resets_the_status(self):
        """RF05: resubmitting sends the EC back to "in_validation", not "rejected"."""
        user = UserFactory(role="requester")
        ec = _ec_with_cd(user)
        _upload(ec, "v1.0")
        reject_ec(ec, ec.responsible_cd, "Corrigir.")

        resubmit_ec(
            ec,
            user,
            SimpleUploadedFile("fix.pdf", b"%PDF-1.4 fix"),
            change_reason="Correção apontada pelo CD.",
        )

        stats = requester_dashboard(user)

        assert stats["by_status"]["in_validation"] == 1
        assert stats["by_status"]["rejected"] == 0
        assert stats["needs_action"] == []
        assert stats["versions_per_document"] == [{"reference": ec.reference, "versions": 2}]

    def test_an_ec_closed_after_routing_to_des_shows_closed_not_approved(self):
        """Issue #96: the dashboard must show `EC.status`, not the latest review.

        An approved EC that was routed to DES is CLOSED, but its latest review
        decision is still "approved" — deriving the status from the review
        made the dashboard read "Aprovado" while /backlog/ec/ showed closed.
        """
        user = UserFactory(role="requester")
        ec = _ec_with_cd(user, release=None)
        _upload(ec, "v1.0")
        approve_ec(ec, ec.responsible_cd)

        from apps.workflow.services import route_to_des

        from apps.workflow.services import route_to_des

        route_to_des(ec, user)

        row = next(
            item for item in requester_dashboard(user)["my_ecs"] if item["id"] == ec.id
        )
        assert row["status"] == EC.Status.CLOSED

    def test_recent_uploads_carry_the_decision_for_the_badge(self):
        """The template renders a badge from `decision`; None means "waiting"."""
        user = UserFactory(role="requester")
        ec = ECFactory(requester=user)
        v1 = _upload(ec, "v1")
        ReviewFactory(document_version=v1, decision=Review.Decision.APPROVED)
        _upload(ec, "v2")

        recent = requester_dashboard(user)["recent_versions"]

        assert recent[0]["version"] == "v2"
        assert recent[0]["decision"] is None  # badge -> "A aguardar CD"
        assert recent[1]["version"] == "v1"
        assert recent[1]["decision"] == Review.Decision.APPROVED
