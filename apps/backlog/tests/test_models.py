"""Model tests for the ERD spec `.opencode/specs/database-scheme.md` sections 4.3 and 4.4."""

import datetime

import pytest
from django.db import IntegrityError, transaction

from apps.backlog.models import EC, Release
from apps.backlog.tests.factories import ECFactory, ReleaseFactory, UserFactory

pytestmark = pytest.mark.django_db


class TestTimeStampedFields:
    """Spec 4.1 - the abstract base exposes created_at / updated_at."""

    def test_release_has_created_at_and_updated_at(self):
        release = ReleaseFactory()

        assert release.created_at is not None
        assert release.updated_at is not None

    def test_ec_has_created_at_and_updated_at(self):
        ec = ECFactory()

        assert ec.created_at is not None
        assert ec.updated_at is not None


class TestRelease:
    """Spec 4.3."""

    def test_defaults(self):
        release = ReleaseFactory()

        assert release.capacity == 10
        assert release.is_open is True
        assert release.production_go_live_date is None

    def test_release_code_is_unique(self):
        ReleaseFactory(release_code="TT_ON_2026-001")

        with pytest.raises(IntegrityError), transaction.atomic():
            ReleaseFactory(release_code="TT_ON_2026-001", year=2027, number_sequence=1)

    def test_year_and_number_sequence_are_unique_together(self):
        ReleaseFactory(year=2026, number_sequence=1)

        with pytest.raises(IntegrityError), transaction.atomic():
            ReleaseFactory(year=2026, number_sequence=1)

    def test_same_number_in_another_year_is_allowed(self):
        first = ReleaseFactory(year=2026, number_sequence=1)
        second = ReleaseFactory(year=2027, number_sequence=1)

        assert first.pk != second.pk

    def test_str_is_the_release_code(self):
        release = ReleaseFactory(release_code="TT_ON_2026-007")

        assert str(release) == "TT_ON_2026-007"

    def test_default_ordering_is_newest_first(self):
        ReleaseFactory(year=2026, number_sequence=1)
        ReleaseFactory(year=2026, number_sequence=2)
        ReleaseFactory(year=2025, number_sequence=9)

        ordered = list(Release.objects.all())

        assert [r.number_sequence for r in ordered] == [2, 1, 9]
        assert ordered[-1].year == 2025

    def test_ec_count_and_is_full(self):
        release = ReleaseFactory(capacity=2)
        ECFactory(release=release)
        ECFactory(release=release)

        assert release.ec_count == 2
        assert release.is_full is True

    def test_is_not_full_below_capacity(self):
        release = ReleaseFactory(capacity=2)
        ECFactory(release=release)

        assert release.is_full is False

    def test_production_go_live_date_is_optional(self):
        release = ReleaseFactory(production_go_live_date=datetime.date(2026, 5, 1))

        assert release.production_go_live_date == datetime.date(2026, 5, 1)


class TestEC:
    """Spec 4.4."""

    def test_status_defaults_to_in_validation(self):
        ec = ECFactory()

        assert ec.status == EC.Status.IN_VALIDATION
        assert ec.status == "in_validation"

    def test_is_imported_defaults_to_false(self):
        assert ECFactory().is_imported is False

    def test_implemented_at_defaults_to_null(self):
        assert ECFactory().implemented_at is None

    def test_ec_code_is_year_and_zero_padded_number(self):
        ec = ECFactory(year=2026, number_sequence=1)

        assert ec.ec_code == "2026-001"

    def test_ec_code_keeps_the_year_visible(self):
        ec = ECFactory(year=2019, number_sequence=42)

        assert ec.ec_code == "2019-042"

    def test_str_is_the_ec_code(self):
        ec = ECFactory(year=2026, number_sequence=7)

        assert str(ec) == "2026-007"

    def test_year_and_number_sequence_are_unique_together(self):
        ECFactory(year=2026, number_sequence=1)

        with pytest.raises(IntegrityError), transaction.atomic():
            ECFactory(year=2026, number_sequence=1)

    def test_same_number_in_another_year_is_allowed(self):
        first = ECFactory(year=2026, number_sequence=1)
        second = ECFactory(year=2027, number_sequence=1)

        assert first.pk != second.pk

    def test_reference_accepts_free_text_formats(self):
        for reference in ["CR2026003", "RT No. 29411", "COR2026001"]:
            ec = ECFactory(reference=reference)

            assert ec.reference == reference

    def test_legacy_rows_allow_null_optional_fields(self):
        """Open item 4 - imported ECs may have no Release, requester, CD or date."""
        ec = ECFactory(
            release=None,
            requester=None,
            responsible_cd=None,
            creation_date=None,
            is_imported=True,
        )

        assert ec.release is None
        assert ec.requester is None
        assert ec.responsible_cd is None
        assert ec.creation_date is None
        assert ec.is_imported is True

    def test_related_names(self):
        user = UserFactory()
        release = ReleaseFactory()
        ec = ECFactory(requester=user, responsible_cd=user, release=release)

        assert list(user.requested_ecs.all()) == [ec]
        assert list(user.assigned_ecs.all()) == [ec]
        assert list(release.ecs.all()) == [ec]

    def test_default_ordering_is_newest_first(self):
        ECFactory(year=2026, number_sequence=1)
        ECFactory(year=2026, number_sequence=2)

        ordered = list(EC.objects.all())

        assert [ec.number_sequence for ec in ordered] == [2, 1]

    def test_release_cannot_be_deleted_while_ecs_exist(self):
        from django.db.models import ProtectedError

        release = ReleaseFactory()
        ECFactory(release=release)

        with pytest.raises(ProtectedError):
            release.delete()

    def test_all_status_choices_exist(self):
        assert [value for value, _ in EC.Status.choices] == [
            "in_validation",
            "approved",
            "rejected",
            "sent_to_des",
            "closed",
            "cancelled",
        ]
