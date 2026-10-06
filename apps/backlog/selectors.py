from django.db.models import Count, F
from django.db.models.functions import TruncMonth

from apps.backlog.models import EC, Release


def release_with_ec_count():
    """Return a queryset of releases annotated with the number of ECs."""
    return Release.objects.annotate(ec_total=Count("ecs")).order_by("-year", "-number_sequence")


def open_releases_with_ec_count():
    """Open releases with a free seat, annotated — one query, no N+1 in the dropdown."""
    return (
        Release.objects.filter(is_open=True)
        .annotate(ec_total=Count("ecs"))
        .filter(ec_total__lt=F("capacity"))
        .order_by("-year", "-number_sequence")
    )


def dashboard_stats(user) -> dict:
    """Aggregate counters rendered by the dashboard (spec `DASHBOARD.md`)."""
    ec_qs = _visible_ecs(user)
    release_qs = _visible_releases(user)

    status_rows = ec_qs.values("status").annotate(n=Count("id"))
    counts = {row["status"]: row["n"] for row in status_rows}
    ec_by_status = {value: counts.get(value, 0) for value, _label in EC.Status.choices}

    releases = [
        {
            "release_code": row.release_code,
            "capacity": row.capacity,
            "ec_count": row.ec_total,
            "percent": round(row.ec_total / row.capacity * 100) if row.capacity else 0,
        }
        for row in release_qs.annotate(ec_total=Count("ecs"))
    ]

    monthly_rows = (
        ec_qs.exclude(creation_date=None)
        .annotate(month=TruncMonth("creation_date"))
        .values("month")
        .annotate(n=Count("id"))
        .order_by("month")
    )

    return {
        "ec_total": ec_qs.count(),
        "ec_by_status": ec_by_status,
        "ec_open": counts.get(EC.Status.IN_VALIDATION, 0),
        "releases": releases,
        "releases_open": release_qs.filter(is_open=True).count(),
        "ec_by_month": [
            {"month": row["month"].strftime("%Y-%m"), "count": row["n"]} for row in monthly_rows
        ],
    }


def _visible_ecs(user):
    """Every EC this user is allowed to count."""
    ecs = EC.objects.all()
    if user.role == "requester":
        return ecs.filter(requester=user)
    if user.role == "cd":
        return ecs.filter(responsible_cd=user)
    if user.role == "des_team":
        return ecs.filter(status=EC.Status.SENT_TO_DES)
    return ecs


def _visible_releases(user):
    """Requester never sees the whole capacity board."""
    if user.role == "requester":
        return Release.objects.none()
    return Release.objects.all().order_by("-year", "-number_sequence")


def requester_dashboard(user) -> dict:
    """EC-centric status breakdown and document metrics for the requester dashboard.

    `by_status` aggregates the user's ECs by their database `status`
    (`in_validation`, `approved`, `rejected`, `sent_to_des`, `closed`),
    excluding cancelled.
    """
    ec_qs = EC.objects.filter(requester=user).exclude(status=EC.Status.CANCELLED)

    rows = list(
        ec_qs.values(
            "id",
            "reference",
            "status",
            "versions__id",
            "versions__version_number",
            "versions__uploaded_at",
            "versions__review__decision",
            "versions__review__comment",
            "versions__review__decided_at",
            "versions__review__cd__username",
        )
    )

    ecs = {}
    for row in rows:
        bucket = ecs.setdefault(
            row["id"],
            {"reference": row["reference"], "db_status": row["status"], "versions": []},
        )
        if row["versions__id"] is not None:
            bucket["versions"].append(row)

    by_status = {value: 0 for value, _label in EC.Status.choices if value != EC.Status.CANCELLED}
    needs_action = []
    versions_per_document = []
    total_versions = 0

    for ec_id, data in ecs.items():
        versions = sorted(data["versions"], key=lambda row: row["versions__id"])
        total_versions += len(versions)

        if versions:
            versions_per_document.append(
                {"reference": data["reference"], "versions": len(versions)}
            )
            latest = versions[-1]
            decision = latest["versions__review__decision"]
            if decision == "approved":
                st = EC.Status.APPROVED
            elif decision == "rejected":
                st = EC.Status.REJECTED
                needs_action.append(
                    {
                        "id": ec_id,
                        "reference": data["reference"],
                        "version": latest["versions__version_number"],
                        "comment": latest["versions__review__comment"],
                        "cd": latest["versions__review__cd__username"],
                        "decided_at": latest["versions__review__decided_at"],
                    }
                )
            else:
                st = data["db_status"]
        else:
            st = data["db_status"]

        if st in by_status:
            by_status[st] += 1

    return {
        "ec_total": len(ecs),
        "versions_total": total_versions,
        "by_status": by_status,
        "needs_action": sorted(needs_action, key=lambda item: item["decided_at"], reverse=True),
        "versions_per_document": sorted(
            versions_per_document, key=lambda item: (-item["versions"], item["reference"])
        ),
        "recent_versions": _recent_uploads(rows),
    }


def _recent_uploads(rows, limit=5):
    """The newest document versions, each with the decision it carries (if any).

    `decision is None` means "still waiting for the CD".
    """
    uploads = [
        {
            "reference": row["reference"],
            "version": row["versions__version_number"],
            "uploaded_at": row["versions__uploaded_at"],
            "decision": row["versions__review__decision"],
        }
        for row in rows
        if row["versions__id"] is not None
    ]
    uploads.sort(key=lambda item: item["uploaded_at"], reverse=True)
    return uploads[:limit]
