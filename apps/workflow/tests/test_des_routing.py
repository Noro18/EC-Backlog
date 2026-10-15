import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.models import Review
from apps.workflow.services import approve_ec, route_to_des

pytestmark = pytest.mark.django_db


def _approved_ec(**kwargs):
    """Setup helper: EC with v1.0 on a release, approved by its CD."""
    requester = UserFactory(role=User.Role.REQUESTER)
    cd = UserFactory(role=User.Role.CD)
    kwargs.setdefault("release", ReleaseFactory())
    ec = ECFactory(requester=requester, responsible_cd=cd, **kwargs)
    DocumentVersionFactory(ec=ec, version_number="v1.0")
    approve_ec(ec, cd)
    return ec, requester, cd


class TestRouteToDES:
    def test_happy_path_closes_ec(self):
        ec, requester, _cd = _approved_ec()

        result = route_to_des(ec, requester)

        assert result.status == EC.Status.CLOSED
        assert ec.versions.count() == 1
        assert Review.objects.count() == 1

    def test_last_ec_closes_the_release(self):
        ec, requester, _cd = _approved_ec()

        route_to_des(ec, requester)

        ec.release.refresh_from_db()
        assert ec.release.is_open is False

    def test_open_sibling_keeps_release_open(self):
        release = ReleaseFactory()
        ec, requester, _cd = _approved_ec(release=release)
        other_requester = UserFactory(role=User.Role.REQUESTER)
        other = ECFactory(
            requester=other_requester,
            responsible_cd=UserFactory(role=User.Role.CD),
            release=release,
        )
        DocumentVersionFactory(ec=other, version_number="v1.0")

        route_to_des(ec, requester)

        release.refresh_from_db()
        assert release.is_open is True
        assert other.status == EC.Status.IN_VALIDATION

    def test_wrong_status_fails(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(requester=requester, responsible_cd=cd, release=ReleaseFactory())
        DocumentVersionFactory(ec=ec, version_number="v1.0")

        with pytest.raises(ValidationError):
            route_to_des(ec, requester)

        ec.refresh_from_db()
        assert ec.status == EC.Status.IN_VALIDATION

    def test_approving_cd_cannot_route(self):
        ec, _requester, cd = _approved_ec()

        with pytest.raises(PermissionDenied):
            route_to_des(ec, cd)

        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED

    def test_stranger_cannot_route(self):
        ec, _requester, _cd = _approved_ec()
        stranger = UserFactory(role=User.Role.REQUESTER)

        with pytest.raises(PermissionDenied):
            route_to_des(ec, stranger)

        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED

    def test_reroute_fails(self):
        ec, requester, _cd = _approved_ec()
        route_to_des(ec, requester)

        with pytest.raises(ValidationError):
            route_to_des(ec, requester)

    def test_des_gets_mailed_on_routing(self):
        ec, requester, _cd = _approved_ec()
        des = UserFactory(role=User.Role.DES_TEAM)

        with TestCase.captureOnCommitCallbacks(execute=True):
            route_to_des(ec, requester)

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [des.email]
        assert "DES" in mail.outbox[0].subject


def _route_url(ec):
    return reverse("workflow:route_to_des", args=[ec.pk])


class TestRouteToDESView:
    def test_cd_post_gets_forbidden(self, client):
        ec, _requester, cd = _approved_ec()
        client.force_login(cd)

        assert client.post(_route_url(ec)).status_code == 403
        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED

    def test_requester_post_routes(self, client):
        ec, requester, _cd = _approved_ec()
        client.force_login(requester)

        response = client.post(_route_url(ec))

        assert response.status_code == 302
        assert response.url == reverse("backlog:ec_detail", args=[ec.pk])
        ec.refresh_from_db()
        assert ec.status == EC.Status.CLOSED

    def test_get_never_routes(self, client):
        ec, requester, _cd = _approved_ec()
        client.force_login(requester)

        assert client.get(_route_url(ec)).status_code == 405
        ec.refresh_from_db()
        assert ec.status == EC.Status.APPROVED
