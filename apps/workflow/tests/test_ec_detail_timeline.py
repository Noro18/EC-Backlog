"""EC detail timeline events that depend on a CD decision.

These tests need `workflow.Review`, so they cannot live in
`apps/backlog/tests/` — ARCHITECTURE §5 forbids `backlog` from importing
`workflow`, and that rule covers test modules too. `workflow` sits at the
top of the arrow chain, so it may read everything below it.

Spec: `.opencode/specs/EC_DETAIL_VIEW.md` (tests 12–14).
"""

import pytest
from django.urls import reverse

from apps.backlog.tests.factories import ECFactory
from apps.workflow.models import Review
from apps.workflow.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db


def _upload(ec, version):
    """Attach a document version through the reverse manager (no documents import)."""
    return ec.versions.create(
        version_number=version, file="documents/spec.pdf", uploaded_by=ec.requester
    )


class TestECDetailDecisionEvents:
    def test_approval_shows_the_pt_label(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        version = _upload(ec, "v1.0")
        review = ReviewFactory(document_version=version, decision=Review.Decision.APPROVED)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        timeline = response.context["timeline"]

        assert "Decisão do CD: Aprovado" in [event["title"] for event in timeline]
        event = timeline[-1]
        assert event["who"] == review.cd.full_name
        assert event["when"] == review.decided_at
        assert event["note"] == review.comment

    def test_rejection_shows_the_comment(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        version = _upload(ec, "v1.0")
        ReviewFactory(
            document_version=version,
            decision=Review.Decision.REJECTED,
            comment="Corrigir a descrição do impacto.",
        )

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        timeline = response.context["timeline"]

        assert "Decisão do CD: Rejeitado" in [event["title"] for event in timeline]
        assert timeline[-1]["note"] == "Corrigir a descrição do impacto."
        html = response.content.decode()
        assert "Decisão do CD: Rejeitado" in html
        assert "Corrigir a descrição do impacto." in html

    def test_decision_event_follows_the_upload_oldest_first(self, client):
        ec = ECFactory()
        client.force_login(ec.requester)
        version = _upload(ec, "v1.0")
        ReviewFactory(document_version=version, decision=Review.Decision.APPROVED)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        timeline = response.context["timeline"]

        assert [event["title"] for event in timeline] == [
            "EC criada",
            "Documento v1.0 carregado",
            "Decisão do CD: Aprovado",
        ]
