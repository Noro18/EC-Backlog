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
from apps.workflow.services import approve_ec, route_to_des

pytestmark = pytest.mark.django_db


def _approved_ec(cd=None):
    """Setup helper: an approved EC (v1.0 reviewed) assigned to cd."""
    cd = cd or UserFactory(role=User.Role.CD)
    requester = UserFactory(role=User.Role.REQUESTER)
    ec = ECFactory(requester=requester, responsible_cd=cd)
    DocumentVersionFactory(ec=ec, version_number="v1.0")
    approve_ec(ec, cd)
    return ec, requester, cd


def _route_url(ec):
    return reverse("workflow:route_to_des", args=[ec.pk])


class TestRouteToDES:
    def test_happy_path_flips_status_without_new_rows(self):
        ec, _requester, cd = _approved_ec()
        reviews_before = Review.objects.count()

        route_to_des(ec, cd)

        assert ec.status == EC.Status.SENT_TO_DES
        assert Review.objects.count() == reviews_before
        assert ec.versions.count() == 1

    def test_non_approved_ec_fails(self):
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(responsible_cd=cd)
        DocumentVersionFactory(ec=ec, version_number="v1.0")

        with pytest.raises(ValidationError):
            route_to_des(ec, cd)

        ec.refresh_from_db()
        assert ec.status == EC.Status.IN_VALIDATION

    def test_stranger_cannot_route(self):
        ec, _requester, _cd = _approved_ec()
        stranger = UserFactory(role=User.Role.CD)

        with pytest.raises(PermissionDenied):
            route_to_des(ec, stranger)

        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED

    def test_requester_cannot_route(self):
        ec, requester, _cd = _approved_ec()

        with pytest.raises(PermissionDenied):
            route_to_des(ec, requester)

        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED


class TestRoutedEmail:
    def test_des_team_gets_mailed_on_routing(self):
        ec, _requester, cd = _approved_ec()
        des1 = UserFactory(role=User.Role.DES_TEAM)
        des2 = UserFactory(role=User.Role.DES_TEAM)
        UserFactory(role=User.Role.REQUESTER)  # must not receive it

        with TestCase.captureOnCommitCallbacks(execute=True):
            route_to_des(ec, cd)

        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert sorted(email.to) == sorted([des1.email, des2.email])
        assert ec.ec_code in email.subject
        assert ec.ec_code in email.body


class TestRouteView:
    def test_stranger_gets_forbidden(self, client):
        ec, _requester, _cd = _approved_ec()
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        assert client.get(_route_url(ec)).status_code == 403

    def test_cd_gets_confirm_page(self, client):
        ec, _requester, cd = _approved_ec()
        client.force_login(cd)

        assert client.get(_route_url(ec)).status_code == 200

    def test_cd_can_route_through_the_view(self, client):
        ec, _requester, cd = _approved_ec()
        client.force_login(cd)

        response = client.post(_route_url(ec))

        assert response.status_code == 302
        assert response.url == reverse("backlog:ec_detail", args=[ec.pk])
        ec.refresh_from_db()
        assert ec.status == EC.Status.SENT_TO_DES

    def test_outsider_post_changes_nothing(self, client):
        ec, _requester, _cd = _approved_ec()
        client.force_login(UserFactory(role=User.Role.CD))

        response = client.post(_route_url(ec))

        assert response.status_code == 403
        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED
