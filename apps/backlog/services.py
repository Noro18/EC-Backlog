from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC, Release


def next_ec_number(year: int) -> int:
    """Return the next EC number for a given year."""
    last_ec = EC.objects.filter(year=year).order_by("-number_sequence").first()
    if last_ec is None:
        return 1
    return last_ec.number_sequence + 1


def create_ec(
    *,
    requester,
    reference: str,
    description: str,
    release,
    responsible_cd,
) -> "EC":
    """Create a new EC with the given parameters and return it."""
    with transaction.atomic():
        fresh = Release.objects.select_for_update().get(pk=release.pk)
        if fresh.ec_count >= fresh.capacity or not fresh.is_open:
            raise ValidationError("Release EC limit reached or release is closed.")
        ec = EC.objects.create(
            year=timezone.localdate().year,
            number_sequence=next_ec_number(timezone.localdate().year),
            reference=reference,
            description=description,
            requester=requester,
            release=fresh,
            responsible_cd=responsible_cd,
            creation_date=timezone.localdate(),
        )
        return ec


def record_go_live(release: Release, user, go_live_date=None) -> Release:
    """RF04: a requester records the go-live date on a closed Release.
    Overwriting is allowed (corrections happen); auditlog records it."""
    if release.is_open:
        raise ValidationError("Go-live can only be recorded on a closed Release.")
    if user.role != User.Role.REQUESTER:
        raise PermissionDenied("Only a requester can record the go-live date.")
    if go_live_date is None:
        raise ValidationError("A go-live date is required.")
    release.production_go_live_date = go_live_date
    release.save(update_fields=["production_go_live_date"])
    return release
