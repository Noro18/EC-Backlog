from apps.backlog.models import EC


def latest_version(ec: EC):
    """Return the newest DocumentVersion of this EC, or None if it has none."""

    return ec.versions.order_by("-uploaded_at").first()
