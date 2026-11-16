import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.backlog.models import EC
from apps.backlog.tests.factories import ECFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_administrator_can_view_audit_log(client):
    admin = UserFactory(role="administrator")
    client.force_login(admin)
    response = client.get(reverse("backlog:audit_log"))
    assert response.status_code == 200
    assert "Registo de Auditoria" in response.content.decode("utf-8")


def test_audit_log_timestamp_uses_dd_mon_yyyy(client):
    admin = UserFactory(role="administrator")
    ec = ECFactory(requester=admin)
    entry = LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(EC),
        object_pk=str(ec.pk),
        action=LogEntry.Action.CREATE,
    ).first()
    assert entry is not None

    client.force_login(admin)
    html = client.get(reverse("backlog:audit_log")).content.decode()

    assert timezone.localtime(entry.timestamp).strftime("%d-%b-%Y %H:%M") in html
    assert entry.timestamp.strftime("%d/%m/%Y") not in html


@pytest.mark.parametrize("role", ["requester", "cd", "des_team"])
def test_non_administrators_get_forbidden(client, role):
    user = UserFactory(role=role)
    client.force_login(user)
    response = client.get(reverse("backlog:audit_log"))
    assert response.status_code == 403


def test_anonymous_redirects_to_login(client):
    response = client.get(reverse("backlog:audit_log"))
    assert response.status_code == 302
    assert "?next=" in response.url
