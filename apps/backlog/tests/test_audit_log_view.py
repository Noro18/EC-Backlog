import pytest
from django.urls import reverse

from apps.backlog.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_administrator_can_view_audit_log(client):
    admin = UserFactory(role="administrator")
    client.force_login(admin)
    response = client.get(reverse("backlog:audit_log"))
    assert response.status_code == 200
    assert "Registo de Auditoria" in response.content.decode("utf-8")


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
