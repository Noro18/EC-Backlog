import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.backlog.services import create_ec, next_ec_number
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestNextEcNumber:
    """EC_CREATE.md tests 1-2 (RF01) + Assumption 2 regression guard."""

    def test_empty_year_return_one(self):
        assert next_ec_number(2026) == 1

    def test_gaps_are_never_reused(self):
        ECFactory(year=2026, number_sequence=1)
        ECFactory(year=2026, number_sequence=2)
        ECFactory(year=2026, number_sequence=3)
        ECFactory(year=2026, number_sequence=6)

        assert next_ec_number(2026) == 7

    def test_numbering_follows_ec_year_not_release_year(self):
        """EC_CREATE.md Assumption 2: a 2027 EC on a 2026 release is numbered in 2027."""
        release_2026 = ReleaseFactory(year=2026, number_sequence=1)
        release_2027 = ReleaseFactory(year=2027, number_sequence=1)
        ECFactory(release=release_2026, year=2027, number_sequence=4)
        ECFactory(release=release_2027, year=2026, number_sequence=1)

        assert next_ec_number(2026) == 2
        assert next_ec_number(2027) == 5


class TestCreateEc:
    """EC_CREATE.md test 3: identity fields set by the service, status left at default."""

    def test_create_ec_sets_identity_and_leaves_status_alone(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory(year=2026, number_sequence=1)

        ec = create_ec(
            requester=requester,
            reference="CR-2026-001",
            description="Test EC description",
            release=release,
            responsible_cd=cd,
        )

        assert ec.requester is requester
        assert ec.reference == "CR-2026-001"
        assert ec.description == "Test EC description"
        assert ec.release == release
        assert ec.responsible_cd is cd
        assert ec.year == timezone.localdate().year
        assert ec.number_sequence == 1
        assert ec.ec_code == f"{ec.year}-{ec.number_sequence:03d}"
        assert ec.creation_date == timezone.localdate()
        assert ec.status == EC.Status.IN_VALIDATION
        assert ec.is_imported is False
