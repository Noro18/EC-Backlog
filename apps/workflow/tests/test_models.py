"""Model tests for the ERD spec `.opencode/specs/database-scheme.md` section 4.6."""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.backlog.tests.factories import UserFactory
from apps.documents.tests.factories import DocumentVersionFactory
from apps.workflow.models import Review
from apps.workflow.tests.factories import ReviewFactory

User = get_user_model()

pytestmark = pytest.mark.django_db


class TestReview:
    """Spec 4.6."""

    def test_review_creation(self):
        review = ReviewFactory()

        assert review.document_version is not None
        assert review.cd is not None
        assert review.decision == Review.Decision.APPROVED
        assert review.comment.startswith("Review comment")
        assert review.decided_at is not None

    def test_decision_choices(self):
        assert [value for value, _ in Review.Decision.choices] == [
            "approved",
            "rejected",
        ]

    def test_valid_review_passes_validation(self):
        review = ReviewFactory()

        review.full_clean()

    def test_comment_is_optional_when_approved(self):
        review = ReviewFactory(decision=Review.Decision.APPROVED, comment="")

        review.full_clean()

    def test_default_ordering_is_newest_first(self):
        ReviewFactory()
        second = ReviewFactory()

        ordered = list(Review.objects.all())

        assert ordered[0] == second


class TestRejectionRequiresComment:
    """Spec 4.6 + 7.5 - rejecting without a comment must fail at both layers."""

    def test_rejected_with_comment_is_allowed(self):
        review = ReviewFactory(
            decision=Review.Decision.REJECTED,
            comment="Missing cost estimate",
        )

        review.full_clean()

    def test_rejected_without_comment_is_rejected_by_validation(self):
        review = ReviewFactory.build(
            document_version=DocumentVersionFactory(),
            cd=UserFactory(),
            decision=Review.Decision.REJECTED,
            comment="",
        )

        with pytest.raises(ValidationError) as excinfo:
            review.full_clean()

        assert "review_rejection_requires_comment" in str(excinfo.value)

    def test_rejected_without_comment_is_blocked_by_the_database(self):
        review = Review(
            document_version=DocumentVersionFactory(),
            cd=UserFactory(),
            decision=Review.Decision.REJECTED,
            comment="",
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            review.save()


class TestOneReviewPerVersion:
    """Spec 4.6 - `document_version` is a OneToOneField, so one row per version."""

    def test_only_one_review_per_version(self):
        review = ReviewFactory()

        with pytest.raises(IntegrityError), transaction.atomic():
            ReviewFactory(document_version=review.document_version, cd=UserFactory())

    def test_review_is_reachable_from_the_version(self):
        review = ReviewFactory()

        assert review.document_version.review == review

    def test_version_without_a_review_is_pending(self):
        """Spec 4.6 - a version with no review row is pending.

        Django's reverse OneToOne raises `RelatedObjectDoesNotExist` rather
        than returning `None`, but that exception subclasses AttributeError,
        so `getattr` with a default is the safe way to ask.
        """
        version = DocumentVersionFactory()

        assert not Review.objects.filter(document_version=version).exists()
        assert getattr(version, "review", None) is None

        # with pytest.raises(DocumentVersion.review.RelatedObjectDoesNotExist):
        #     version.review


class TestRelationships:
    """Spec 5."""

    def test_cd_reviews_returns_every_decision_that_cd_made(self):
        cd = UserFactory(role=User.Role.CD)
        first = ReviewFactory(cd=cd)
        second = ReviewFactory(cd=cd)

        assert list(cd.cd_reviews.all()) == [second, first]

    def test_cannot_delete_a_user_who_has_reviewed(self):
        from django.db.models import ProtectedError

        review = ReviewFactory()

        with pytest.raises(ProtectedError):
            review.cd.delete()

    def test_cannot_delete_a_document_version_that_was_reviewed(self):
        from django.db.models import ProtectedError

        review = ReviewFactory()

        with pytest.raises(ProtectedError):
            review.document_version.delete()
