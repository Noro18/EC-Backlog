import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC, Release
from apps.backlog.services import (
    can_edit_ec,
    create_ec,
    create_release,
    next_ec_number,
    update_ec,
)
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


class TestCreateEcCapacity:
    """EC_CREATE.md tests 4-6: capacity and open/closed rules are the service's law."""

    def test_11th_ec_is_refused(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory(capacity=10)
        for seq in range(1, 11):
            ECFactory(release=release, year=2026, number_sequence=seq)

        with pytest.raises(ValidationError):
            create_ec(
                requester=requester,
                reference="CR-2026-011",
                description="Should not fit",
                release=release,
                responsible_cd=cd,
            )

        assert release.ec_count == 10

    def test_capacity_is_rechecked_in_the_service_not_only_the_form(self):
        """Test 5: a caller holding a stale release instance still cannot exceed capacity."""
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory(capacity=2)
        stale = Release.objects.get(pk=release.pk)  # snapshot: sees 0/2

        ECFactory(release=release, year=2026, number_sequence=1)
        ECFactory(release=release, year=2026, number_sequence=2)  # now full; stale still 0/2

        with pytest.raises(ValidationError):
            create_ec(
                requester=requester,
                reference="CR-2026-003",
                description="Skips the form's disabled option",
                release=stale,
                responsible_cd=cd,
            )

    def test_closed_release_refuses_new_ecs(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        cd = UserFactory(role=User.Role.CD)
        release = ReleaseFactory(capacity=10, is_open=False)  # room, but closed

        with pytest.raises(ValidationError):
            create_ec(
                requester=requester,
                reference="CR-2026-012",
                description="Closed release must refuse",
                release=release,
                responsible_cd=cd,
            )


class TestCreateRelease:
    """RELEASE_CREATE_ON_DEMAND.md (RF02): minting the next Release on demand."""

    def test_empty_year_starts_at_001(self):
        release = create_release()
        year = timezone.localdate().year
        assert release.release_code == f"TT_ON_{year}-001"
        assert (release.year, release.number_sequence) == (year, 1)
        assert release.capacity == 10
        assert release.is_open is True

    def test_continues_sequence_of_current_year(self):
        year = timezone.localdate().year
        ReleaseFactory(year=year, number_sequence=3)

        release = create_release()

        assert release.release_code == f"TT_ON_{year}-004"

    def test_ignores_other_years(self):
        year = timezone.localdate().year
        ReleaseFactory(year=year - 1, number_sequence=99)

        release = create_release()

        assert release.release_code == f"TT_ON_{year}-001"

    def test_retries_on_race(self, monkeypatch):
        real_create = Release.objects.create
        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise IntegrityError("simulated concurrent mint")
            return real_create(**kwargs)

        monkeypatch.setattr(Release.objects, "create", flaky)

        release = create_release()

        assert calls["n"] == 2
        assert Release.objects.count() == 1
        assert release.number_sequence == 1


class TestUpdateEC:
    """EC_EDIT.md (issue #67): the rules for editing an EC that is still in flight."""

    def _edit(self, ec, user, **overrides):
        data = {
            "reference": ec.reference,
            "description": ec.description,
            "release": ec.release,
            "responsible_cd": ec.responsible_cd,
        }
        data.update(overrides)
        return update_ec(ec, user, **data)

    def test_owner_updates_the_content(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)

        updated = self._edit(
            ec, requester, reference="CR2026999", description="Descrição revista"
        )

        assert updated.reference == "CR2026999"
        assert updated.description == "Descrição revista"
        assert updated.status == EC.Status.IN_VALIDATION

    def test_owner_moves_the_ec_to_another_open_release(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)
        target = ReleaseFactory(year=2027, number_sequence=1, capacity=10)

        updated = self._edit(ec, requester, release=target)

        assert updated.release == target

    def test_rejected_ec_can_still_be_edited(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.REJECTED)

        updated = self._edit(ec, requester, description="Correção de texto")

        assert updated.description == "Correção de texto"

    def test_non_owner_requester_is_refused(self):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        intruder = UserFactory(role=User.Role.REQUESTER)

        with pytest.raises(PermissionDenied):
            self._edit(ec, intruder, reference="CR2026888")

    def test_cd_cannot_edit(self):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        cd = UserFactory(role=User.Role.CD)

        with pytest.raises(PermissionDenied):
            self._edit(ec, cd, reference="CR2026888")

    def test_des_team_cannot_edit(self):
        ec = ECFactory(status=EC.Status.IN_VALIDATION)
        des = UserFactory(role=User.Role.DES_TEAM)

        with pytest.raises(PermissionDenied):
            self._edit(ec, des, reference="CR2026888")

    def test_administrator_may_edit_any_ec(self):
        admin = UserFactory(role=User.Role.ADMINISTRATOR)
        ec = ECFactory(status=EC.Status.IN_VALIDATION, requester=None)

        updated = self._edit(ec, admin, reference="CR2026777")

        assert updated.reference == "CR2026777"

    @pytest.mark.parametrize(
        "status",
        [
            EC.Status.APPROVED,
            EC.Status.SENT_TO_DES,
            EC.Status.CLOSED,
            EC.Status.CANCELLED,
        ],
    )
    def test_terminal_statuses_are_refused(self, status):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=status)

        with pytest.raises(PermissionDenied):
            self._edit(ec, requester, reference="CR2026888")

    def test_full_target_release_is_refused(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)
        target = ReleaseFactory(year=2027, number_sequence=2, capacity=1)
        ECFactory(release=target, year=2027, number_sequence=1)

        with pytest.raises(ValidationError):
            self._edit(ec, requester, release=target)

        ec.refresh_from_db()
        assert ec.release != target

    def test_closed_target_release_is_refused(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)
        target = ReleaseFactory(year=2027, number_sequence=3, is_open=False)

        with pytest.raises(ValidationError):
            self._edit(ec, requester, release=target)

    def test_keeping_the_current_full_release_works(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        release = ReleaseFactory(capacity=1)
        ec = ECFactory(requester=requester, release=release, status=EC.Status.IN_VALIDATION)

        updated = self._edit(ec, requester, reference="CR2026777")

        assert updated.reference == "CR2026777"
        assert updated.release == release

    def test_can_edit_ec_predicate(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)

        assert can_edit_ec(ec, requester) is True
        assert can_edit_ec(ec, UserFactory(role=User.Role.CD)) is False
        ec.status = EC.Status.CLOSED
        assert can_edit_ec(ec, requester) is False

    def test_owner_changes_the_responsible_cd(self):
        requester = UserFactory(role=User.Role.REQUESTER)
        old_cd = UserFactory(role=User.Role.CD)
        new_cd = UserFactory(role=User.Role.CD)
        ec = ECFactory(
            requester=requester, responsible_cd=old_cd, status=EC.Status.IN_VALIDATION
        )

        updated = self._edit(ec, requester, responsible_cd=new_cd)

        assert updated.responsible_cd == new_cd

    @pytest.mark.parametrize("role", [User.Role.REQUESTER, User.Role.DES_TEAM])
    def test_the_responsible_must_be_a_cd(self, role):
        requester = UserFactory(role=User.Role.REQUESTER)
        ec = ECFactory(requester=requester, status=EC.Status.IN_VALIDATION)
        wrong = UserFactory(role=role)

        with pytest.raises(ValidationError):
            self._edit(ec, requester, responsible_cd=wrong, reference="CR2026111")

        ec.refresh_from_db()
        assert ec.reference != "CR2026111"
        assert ec.responsible_cd_id != wrong.pk
