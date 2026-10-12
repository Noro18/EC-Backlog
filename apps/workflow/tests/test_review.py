import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.models import Review
from apps.workflow.selectors import latest_version
from apps.workflow.services import approve_ec, reject_ec

pytestmark = pytest.mark.django_db


class TestLatestVersion:
    def test_returns_the_newest_version(self):
        ec = ECFactory()
        DocumentVersionFactory(ec=ec, version_number="v1.0")
        DocumentVersionFactory(ec=ec, version_number="v1.1")

        assert latest_version(ec).version_number == "v1.1"

    def test_returns_none_when_no_versions(self):
        ec = ECFactory()
        assert latest_version(ec) is None


def _ec_with_version(cd=None):
    """Setup helper: an in_validation EC assigned to cd, with v1.0."""
    cd = cd or UserFactory(role=User.Role.CD)
    ec = ECFactory(responsible_cd=cd)
    version = DocumentVersionFactory(ec=ec, version_number="v1.0")
    return ec, cd, version


class TestApproveEC:
    def test_approve_flips_status_and_records_review(self):
        ec, cd, version = _ec_with_version()

        review = approve_ec(ec, cd)

        assert review.decision == Review.Decision.APPROVED
        assert review.document_version == version
        assert review.cd == cd
        assert ec.status == EC.Status.APPROVED

    def test_second_decision_fails(self):
        ec, cd, _version = _ec_with_version()
        approve_ec(ec, cd)

        with pytest.raises(ValidationError):  # expect to
            approve_ec(ec, cd)

        assert Review.objects.count() == 1

    def test_stranger_cd_cannot_decide(self):
        ec, _cd, _version = _ec_with_version()
        stranger = UserFactory(role=User.Role.CD)

        with pytest.raises(PermissionDenied):
            approve_ec(ec, stranger)

        ec.refresh_from_db()
        assert ec.status == EC.Status.IN_VALIDATION
        assert Review.objects.count() == 0


class TestRejectEC:
    def test_reject_stores_comment_and_flips_status(self):
        ec, cd, version = _ec_with_version()

        review = reject_ec(ec, cd, "Falta o diagrama unifilar")

        assert review.decision == Review.Decision.REJECTED
        assert review.comment == "Falta o diagrama unifilar"
        assert review.document_version == version
        assert ec.status == EC.Status.REJECTED

    def test_blank_comment_rejected(self):
        ec, cd, _version = _ec_with_version()

        with pytest.raises(ValidationError):
            reject_ec(ec, cd, "   ")

        ec.refresh_from_db()
        assert ec.status == EC.Status.IN_VALIDATION
        assert Review.objects.count() == 0


class TestDecisionEmail:
    def test_approval_queues_email_to_requester(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")

        with TestCase.captureOnCommitCallbacks(execute=True):
            approve_ec(ec, cd)

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [requester.email]
        assert "aprovada" in email.subject
        assert ec.ec_code in email.subject

    def test_rejection_email_carries_the_reason(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")

        with TestCase.captureOnCommitCallbacks(execute=True):
            reject_ec(ec, cd, "Falta o diagrama unifilar")

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [requester.email]
        assert "rejeitada" in email.subject
        assert "Falta o diagrama unifilar" in email.body


def _review_url(ec):
    from django.urls import reverse

    return reverse("workflow:review_ec", args=[ec.pk])


class TestReviewView:
    def test_stranger_cd_gets_forbidden(self, client):
        ec, _cd, _version = _ec_with_version()
        stranger = UserFactory(role=User.Role.CD)
        client.force_login(stranger)

        response = client.get(_review_url(ec))

        assert response.status_code == 403

    def test_cd_can_approve_through_the_view(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")
        client.force_login(cd)

        response = client.post(_review_url(ec), {"decision": "approve", "comment": ""})

        assert response.status_code == 302
        assert response.url == reverse("backlog:ec_detail", args=[ec.pk])
        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED

    def test_reject_without_comment_shows_form_error(self, client):
        ec, cd, _version = _ec_with_version()
        client.force_login(cd)

        response = client.post(_review_url(ec), {"decision": "reject", "comment": ""})

        assert response.status_code == 200
        ec.refresh_from_db()
        assert ec.status == EC.Status.IN_VALIDATION
        assert Review.objects.count() == 0
