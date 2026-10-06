"""Requester dashboard widgets that depend on a CD decision.

These tests need `workflow.Review`, so they cannot live in
`apps/backlog/tests/` — ARCHITECTURE §5 forbids `backlog` from importing
`workflow`, and that rule covers test modules too. `workflow` sits at the
top of the arrow chain, so it may read everything below it.
"""

import pytest

from apps.backlog.selectors import requester_dashboard
from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.workflow.models import Review
from apps.workflow.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db


def _upload(ec, version):
    """Attach a document version through the reverse manager (no documents import)."""
    return ec.versions.create(
        version_number=version, file="documents/spec.pdf", uploaded_by=ec.requester
    )


class TestRequesterDecisions:
    def test_approval_on_the_latest_version_counts_as_approved(self):
        user = UserFactory(role="requester")
        version = _upload(ECFactory(requester=user), "v1")
        ReviewFactory(document_version=version, decision=Review.Decision.APPROVED)

        assert requester_dashboard(user)["by_status"]["approved"] == 1

    def test_rejection_lands_in_needs_action_with_the_comment(self):
        user = UserFactory(role="requester")
        ec = ECFactory(requester=user)
        version = _upload(ec, "v1")
        ReviewFactory(
            document_version=version,
            decision=Review.Decision.REJECTED,
            comment="Falta a justificação do impacto.",
        )

        stats = requester_dashboard(user)

        assert stats["by_status"]["rejected"] == 1
        assert stats["needs_action"][0]["reference"] == ec.reference
        assert stats["needs_action"][0]["comment"] == "Falta a justificação do impacto."
        # The EC id drives the link to the detail page in the template.
        assert stats["needs_action"][0]["id"] == ec.id

    def test_a_new_upload_after_a_rejection_resets_the_status(self):
        """RF05: uploading again sends the EC back to "in_validation", not "rejected"."""
        user = UserFactory(role="requester")
        ec = ECFactory(requester=user)
        v1 = _upload(ec, "v1")
        ReviewFactory(document_version=v1, decision=Review.Decision.REJECTED, comment="Corrigir.")
        _upload(ec, "v2")

        stats = requester_dashboard(user)

        assert stats["by_status"]["in_validation"] == 1
        assert stats["by_status"]["rejected"] == 0
        assert stats["needs_action"] == []
        assert stats["versions_per_document"] == [{"reference": ec.reference, "versions": 2}]

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
