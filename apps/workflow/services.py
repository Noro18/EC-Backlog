from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.backlog.models import EC
from apps.documents.models import DocumentVersion  # workflow → documents: downward, allowed
from apps.workflow.models import Review
from apps.workflow.notifications import queue_decision_made
from apps.workflow.selectors import latest_version


def _decidable_version(ec: EC, cd) -> DocumentVersion:
    """Shared guards for both decisions: return the latest unreviewed
    version, or raise. One home for the three guards so approve/reject
    can never disagree about who may decide what, when."""
    if ec.status != EC.Status.IN_VALIDATION:
        raise ValidationError("This EC is no longer awaiting validation.")
    if (
        cd.pk != ec.responsible_cd_id
    ):  # sae quearddeit ih logic app nian, nanti iha UI sei halo authz hotu
        raise PermissionDenied("Only the assigned CD can decide this EC.")
    version = latest_version(ec)
    if version is None:
        raise ValidationError("This EC has no document version to decide on.")
    try:
        existing_review = version.review
    except Review.DoesNotExist:
        return version  # no decision recorded yet — good, proceed
    raise ValidationError(f"This version was already decided ({existing_review.decision}).")


def approve_ec(ec: EC, cd) -> Review:
    """RF09: record an approval on the latest version and flip status."""
    version = _decidable_version(ec, cd)
    with transaction.atomic():
        review = Review.objects.create(
            document_version=version,
            cd=cd,
            decision=Review.Decision.APPROVED,
            comment="",
        )
        ec.status = EC.Status.APPROVED
        ec.save(update_fields=["status"])
        queue_decision_made(ec)
    return review


def reject_ec(ec: EC, cd, comment: str) -> Review:
    """RF09: record a rejection (comment mandatory) and flip status."""
    version = _decidable_version(ec, cd)
    if not (comment or "").strip():
        raise ValidationError("A reason is required to reject an EC.")
    with transaction.atomic():
        review = Review.objects.create(
            document_version=version,
            cd=cd,
            decision=Review.Decision.REJECTED,
            comment=comment,
        )
        ec.status = EC.Status.REJECTED
        ec.save(update_fields=["status"])
        queue_decision_made(ec)
    return review
