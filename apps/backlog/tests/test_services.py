import pytest

from apps.backlog.services import next_ec_number
from apps.backlog.tests.factories import ECFactory, ReleaseFactory

pytestmark = pytest.mark.django_db


class TestNextEcNumber:
    """EC_CREATE.md tests 1-2 (RF01) + Assumption 2 regression guard."""

    def test_empty_year_return_one(self):
        assert next_ec_number(2026) == 1

    def test_gaps_are_never_reused(self):
        release = ReleaseFactory(year=2026, number_sequence=1)
        ECFactory(release=release, number_sequence=1)
        ECFactory(release=release, number_sequence=2)
        ECFactory(release=release, number_sequence=3)
        ECFactory(release=release, number_sequence=6)

        assert next_ec_number(2026) == 7

    def test_numbering_follows_ec_year_not_release_year(self):
        """EC_CREATE.md Assumption 2: a 2027 EC on a 2026 release is numbered in 2027."""
        release_2026 = ReleaseFactory(year=2026, number_sequence=1)
        release_2027 = ReleaseFactory(year=2027, number_sequence=1)
        ECFactory(release=release_2026, year=2027, number_sequence=4)
        ECFactory(release=release_2027, year=2026, number_sequence=1)

        assert next_ec_number(2026) == 2
        assert next_ec_number(2027) == 5
