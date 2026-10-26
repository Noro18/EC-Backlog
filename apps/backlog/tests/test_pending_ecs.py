from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.tests.factories import ReviewFactory

pytestmark = pytest.mark.django_db


def make_pending_ec(*, cd, requester, number, status=EC.Status.IN_VALIDATION):
    ec = ECFactory(
        year=2027,
        number_sequence=number,
        reference=f"REF{number}",
        requester=requester,
        responsible_cd=cd,
        release=None,
        status=status,
    )
    document = DocumentVersionFactory(
        ec=ec,
        uploaded_by=requester,
        version_number="v1.0",
    )
    return ec, document


class TestPendingECListAccess:
    def test_anonymous_user_is_redirected_to_login(self, client):
        response = client.get(reverse("backlog:pending_ecs"))

        assert response.status_code == 302
        assert "?next=" in response.url

    @pytest.mark.parametrize("role", [User.Role.REQUESTER, User.Role.DES_TEAM])
    def test_requester_and_des_team_are_forbidden(self, client, role):
        client.force_login(UserFactory(role=role))

        response = client.get(reverse("backlog:pending_ecs"))

        assert response.status_code == 403


class TestPendingECList:
    def test_cd_sees_only_unreviewed_ecs_assigned_to_them(self, client):
        cd = UserFactory(role=User.Role.CD)
        another_cd = UserFactory(role=User.Role.CD)
        requester = UserFactory(role=User.Role.REQUESTER)

        own_ec, _ = make_pending_ec(cd=cd, requester=requester, number=1)
        other_cd_ec, _ = make_pending_ec(
            cd=another_cd, requester=requester, number=2
        )

        reviewed_ec, reviewed_document = make_pending_ec(
            cd=cd, requester=requester, number=3
        )
        ReviewFactory(document_version=reviewed_document, cd=cd)

        no_document_ec = ECFactory(
            year=2027,
            number_sequence=4,
            requester=requester,
            responsible_cd=cd,
            release=None,
            status=EC.Status.IN_VALIDATION,
        )

        client.force_login(cd)
        response = client.get(reverse("backlog:pending_ecs"))
        html = response.content.decode()

        assert response.status_code == 200
        assert own_ec.ec_code in html
        assert other_cd_ec.ec_code not in html
        assert reviewed_ec.ec_code not in html
        assert no_document_ec.ec_code not in html

    def test_administrator_sees_pending_ecs_assigned_to_different_cds(self, client):
        first_cd = UserFactory(role=User.Role.CD)
        second_cd = UserFactory(role=User.Role.CD)
        requester = UserFactory(role=User.Role.REQUESTER)

        first_ec, _ = make_pending_ec(cd=first_cd, requester=requester, number=11)
        second_ec, _ = make_pending_ec(cd=second_cd, requester=requester, number=12)

        client.force_login(UserFactory(role=User.Role.ADMINISTRATOR))
        response = client.get(reverse("backlog:pending_ecs"))
        html = response.content.decode()

        assert response.status_code == 200
        assert first_ec.ec_code in html
        assert second_ec.ec_code in html

    def test_empty_queue_shows_empty_state(self, client):
        client.force_login(UserFactory(role=User.Role.CD))

        response = client.get(reverse("backlog:pending_ecs"))

        assert response.status_code == 200
        assert "Nenhum EC pendente de revisão." in response.content.decode()

    def test_newest_document_upload_is_listed_first(self, client):
        cd = UserFactory(role=User.Role.CD)
        requester = UserFactory(role=User.Role.REQUESTER)
        older_ec, older_document = make_pending_ec(
            cd=cd, requester=requester, number=21
        )
        newer_ec, newer_document = make_pending_ec(
            cd=cd, requester=requester, number=22
        )

        now = timezone.now()
        type(older_document).objects.filter(pk=older_document.pk).update(
            uploaded_at=now - timedelta(days=2)
        )
        type(newer_document).objects.filter(pk=newer_document.pk).update(
            uploaded_at=now - timedelta(days=1)
        )

        client.force_login(cd)
        response = client.get(reverse("backlog:pending_ecs"))
        html = response.content.decode()

        assert html.index(newer_ec.ec_code) < html.index(older_ec.ec_code)

    def test_queue_is_paginated_at_25_rows(self, client):
        cd = UserFactory(role=User.Role.CD)
        requester = UserFactory(role=User.Role.REQUESTER)

        for number in range(1, 27):
            make_pending_ec(cd=cd, requester=requester, number=number)

        client.force_login(cd)
        response = client.get(reverse("backlog:pending_ecs"))

        assert response.status_code == 200
        table = response.context["table"]
        assert table.page.paginator.count == 26
        assert len(table.page.object_list) == 25
