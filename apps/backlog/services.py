from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

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
        if fresh.ec_count >= fresh.capacity:
            raise ValidationError("Release EC limit reached")
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
