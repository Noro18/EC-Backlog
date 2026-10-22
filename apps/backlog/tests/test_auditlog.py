import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import ReleaseFactory, UserFactory
from apps.backlog.tests.test_views import docx_file

pytestmark = pytest.mark.django_db


class TestAuditlogActor:
    """RNF02: changes made through a request are recorded with the acting user."""

    def test_creating_an_ec_records_the_actor(self, client):
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
        assert response.status_code == 302  # the EC was really created

        ec = EC.objects.latest("id")
        entry = LogEntry.objects.get(
            content_type=ContentType.objects.get_for_model(EC),
            object_pk=str(ec.pk),
            action=LogEntry.Action.CREATE,
        )

        assert entry.action == LogEntry.Action.CREATE
        assert entry.actor == requester
