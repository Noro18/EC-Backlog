import pytest
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.notifications import send_cd_assigned_email, send_decision_email
from apps.workflow.services import approve_ec

pytestmark = pytest.mark.django_db


class TestCDAssignmentNotification:
    def test_create_ec_sends_email_to_the_cd(self, client):
        req = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        client.force_login(req)
        release = ReleaseFactory()

        with TestCase.captureOnCommitCallbacks(
            execute=True
        ):  # uza ida ne'e tanba transaction.on_commit so bele work se quando transction nebe wrap iha atomic() ne bener bener save duni ba row. maibe tanba iha test ne labele entaun uza captureOnCommitCallbacks
            response = client.post(
                reverse("backlog:ec_form"),
                data={
                    "reference": "CR2026043",
                    "description": "Trocar o resistor R12",
                    "release": release.pk,
                    "responsible_cd": cd.pk,
                },
            )
        assert response.status_code == 302  # the EC was really created

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [cd.email]
        assert EC.objects.latest("id").ec_code in email.subject

    def test_email_body_carries_reference_requester_and_link(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(requester)

        with TestCase.captureOnCommitCallbacks(execute=True):
            client.post(
                reverse("backlog:ec_form"),
                data={
                    "reference": "CR2026044",
                    "description": "Trocar o resistor R12",
                    "release": release.pk,
                    "responsible_cd": cd.pk,
                },
            )

        ec = EC.objects.latest("id")
        body = mail.outbox[0].body
        assert ec.reference in body
        assert (requester.full_name or requester.username) in body
        assert f"{settings.SITE_URL}/backlog/detail_ec/{ec.pk}/" in body

    def test_rollback_sends_no_email(self, client):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory()
        client.force_login(requester)

        with TestCase.captureOnCommitCallbacks(execute=True):
            response = client.post(
                reverse("backlog:ec_form"),
                data={
                    "reference": "CR2026045",
                    "description": "Trocar o resistor R12",
                    "release": release.pk,
                    "responsible_cd": cd.pk,
                    "document": SimpleUploadedFile("spec.txt", b"not a pdf or docx"),
                },
            )

        assert response.status_code == 200  # form re-rendered with the file error
        assert mail.outbox == []
        assert EC.objects.count() == 0

    def test_task_ignores_a_deleted_ec(self):
        send_cd_assigned_email(99999)  # no such EC — deleted before the worker ran
        assert mail.outbox == []

    def test_task_skips_a_cd_without_email(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD, email="")
        ec = ECFactory(requester=requester, responsible_cd=cd)

        send_cd_assigned_email(ec.pk)
        assert mail.outbox == []


class TestDecisionEmailGuards:
    def test_task_ignores_a_deleted_ec(self):
        send_decision_email(99999)  # no such EC — deleted before the worker ran
        assert mail.outbox == []

    def test_task_ignores_an_ec_without_versions(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)

        send_decision_email(ec.pk)
        assert mail.outbox == []

    def test_task_ignores_a_version_without_review(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")

        send_decision_email(ec.pk)
        assert mail.outbox == []

    def test_task_skips_a_requester_without_email(self):
        requester = UserFactory(role=User.Role.REQUESTER, email="")
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")
        approve_ec(ec, cd)

        send_decision_email(ec.pk)
        assert mail.outbox == []
