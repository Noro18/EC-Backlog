from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.backlog.models import EC
from apps.documents.models import DocumentVersion  # workflow → documents: downward, allowed
from apps.documents.services import create_next_version
from apps.workflow.models import Review
from apps.workflow.notifications import queue_cd_assigned, queue_decision_made, queue_routed_to_des
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


def resubmit_ec(ec, user, file, change_reason="", major=False, responsible_cd=None):
    """RF05: requester uploads a fix for a rejected EC — new version row,
    status back to in_validation, CD notified."""
    if ec.status != EC.Status.REJECTED:
        raise ValidationError("Only a rejected EC can be resubmitted.")
    if user.pk != ec.requester_id:
        raise PermissionDenied("Only the requester can resubmit this EC.")
    if responsible_cd is not None and responsible_cd.role != User.Role.CD:
        raise ValidationError("The responsible must be a CD user.")
    with transaction.atomic():
        version = create_next_version(
            ec=ec,
            file=file,
            uploaded_by=user,
            change_reason=change_reason,
            major=major,
        )
        if responsible_cd is not None:
            ec.responsible_cd = responsible_cd
        ec.status = EC.Status.IN_VALIDATION
        ec.save(update_fields=["responsible_cd", "status"])
        queue_cd_assigned(ec)
    return version


def route_to_des(ec: EC, user) -> EC:
    """RF11: the approving CD forwards an approved EC to the DES team."""
    if ec.status != EC.Status.APPROVED:
        raise ValidationError("Only an approved EC can be routed to the DES team.")
    if user.pk != ec.responsible_cd_id:
        raise PermissionDenied("Only the approving CD can route this EC to DES.")
    with transaction.atomic():
        ec.status = EC.Status.SENT_TO_DES
        ec.save(update_fields=["status"])
        queue_routed_to_des(ec)
    return ec
