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
