from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.backlog.models import EC, Release

#: Sentinel posted by the create form when the requester picks
#: "+ Kria Release Foun" instead of an existing Release (RF02).
NEW_RELEASE = "__new__"

#: EC_EDIT.md Decision 3 — content may only be corrected while it is still
#: being shaped, before the CD approves it and before routing closes it.
EDITABLE_STATUSES = (EC.Status.IN_VALIDATION, EC.Status.REJECTED)


def can_edit_ec(ec: "EC", user) -> bool:
    """EC_EDIT.md Decision 2: the owner, or an Administrator."""
    if ec.status not in EDITABLE_STATUSES:
        return False
    return user.role == User.Role.ADMINISTRATOR or ec.requester_id == user.pk


def next_ec_number(year: int) -> int:
    """Return the next EC number for a given year."""
    last_ec = EC.objects.filter(year=year).order_by("-number_sequence").first()
    if last_ec is None:
        return 1
    return last_ec.number_sequence + 1


def create_release() -> Release:
    """RF02: mint the next Release of the current year (`TT_ON_AAAA-NNN`).

    Retries on unique-constraint races (two requesters minting at once):
    the loser re-reads the max sequence and tries the next number.
    """
    year = timezone.localdate().year
    with transaction.atomic():
        for _ in range(3):
            last = Release.objects.filter(year=year).order_by("-number_sequence").first()
            number = last.number_sequence + 1 if last else 1
            try:
                with transaction.atomic():
                    return Release.objects.create(
                        release_code=f"TT_ON_{year}-{number:03d}",
                        year=year,
                        number_sequence=number,
                    )
            except IntegrityError:
                continue
    raise ValidationError("La konsege kria Release; tenta fali.")


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


def update_ec(ec, user, *, reference, description, release, responsible_cd):
    """EC_EDIT.md: correct the content of an EC that is still in flight.

    Status and identity are never written here; a moved Release must be open
    with a free seat, and a reassigned CD must really be a CD. Keeping the
    current Release is always allowed, even if it is now full or closed,
    because the EC already holds its seat.
    """
    with transaction.atomic():
        ec.refresh_from_db()
        if not can_edit_ec(ec, user):
            raise PermissionDenied("This EC cannot be edited.")

        if responsible_cd is not None and responsible_cd.role != User.Role.CD:
            raise ValidationError("The responsible must be a CD user.")

        fields = ["reference", "description"]
        ec.reference = reference
        ec.description = description

        if responsible_cd is not None and responsible_cd.pk != ec.responsible_cd_id:
            ec.responsible_cd = responsible_cd
            fields.append("responsible_cd")

        if release is not None and release.pk != ec.release_id:
            target = Release.objects.get(pk=release.pk)
            if not target.is_open or target.ec_count >= target.capacity:
                raise ValidationError("Release EC limit reached or release is closed.")
            ec.release = target
            fields.append("release")

        ec.save(update_fields=fields)
    return ec