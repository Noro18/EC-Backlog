from django.core.exceptions import ValidationError

from .models import DocumentVersion


def create_first_version(ec, file, uploaded_by, change_reason=""):
    """RF06: store the first document version for an EC — always v1.0 (RF06)."""
    version = DocumentVersion(
        ec=ec,
        version_number="v1.0",
        file=file,
        uploaded_by=uploaded_by,
        change_reason=change_reason,
    )
    version.full_clean()  # Validate before saving
    version.save()
    return version


def create_next_version(ec, file, uploaded_by, change_reason="", major=False):
    """RF05: store a follow-up version — minor bump (v1.0 → v1.1) by default,
    major bump (v1.2 → v2.0) when major=True."""

    if not (change_reason or "").strip():
        raise ValidationError("Change reason must not be empty for a re-upload.")

    latest = ec.versions.order_by("-uploaded_at").first()

    if latest is None:
        raise ValidationError("This EC has no versions yet — upload v1.0 first.")
    pieces = latest.version_number[1:].split(".")
    if len(pieces) != 2:
        raise ValidationError(f"Unknown version format: {latest.version_number}.")
    try:
        current_major = int(pieces[0])
        current_minor = int(pieces[1])
    except ValueError:
        raise ValidationError(f"Unknown version format: {latest.version_number}.")
    if major:
        next_number = f"v{current_major + 1}.0"
    else:
        next_number = f"v{current_major}.{current_minor + 1}"

    version = DocumentVersion(
        ec=ec,
        version_number=next_number,
        file=file,
        uploaded_by=uploaded_by,
        change_reason=change_reason,
    )
    version.full_clean()
    version.save()
    return version
