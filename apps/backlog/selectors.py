import re

from auditlog.models import LogEntry
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.accounts.models import User
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


def releases_for_edit(current):
    """EC_EDIT.md Decision 4: open Releases with a free seat, plus the EC's
    current Release. Keeping the current one must never fail just because it
    has since filled up or closed — the EC already holds its seat."""
    open_with_room = open_releases_with_ec_count()
    allowed = Q(pk__in=open_with_room.values("pk"))
    if current is not None:
        allowed |= Q(pk=current.pk)
    return (
        Release.objects.filter(allowed)
        .annotate(ec_total=Count("ecs"))
        .order_by("-year", "-number_sequence")
    )

def ec_for_edit(current):
    pass


def dashboard_stats(user) -> dict:
    """Aggregate counters rendered by the dashboard (spec `DASHBOARD.md`)."""
    ec_qs = visible_ecs(user)
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


def visible_ecs(user):
    """ECs this user is allowed to see: requester → own, cd → assigned,
    des_team → closed (routed ECs skip sent_to_des), everyone else → all
    (ARCHITECTURE §5: views read this through selectors, never their own query)."""
    ecs = EC.objects.all()
    if user.role == "requester":
        return ecs.filter(requester=user)
    if user.role == "cd":
        return ecs.filter(responsible_cd=user)
    if user.role == "des_team":
        return ecs.filter(status=EC.Status.CLOSED)
    return ecs


def search_ecs(queryset, q=None, status=None):
    """RF12 — the toolbar filters above the EC list. `q` is free text over
    reference, description and the EC id (year / year-sequence); `status`
    matches `EC.Status` exactly. Both are optional and stack."""
    q = (q or "").strip()
    if q:
        text = Q(reference__icontains=q) | Q(description__icontains=q)
        # The table renders ids as "EC-2019-012", so users may type the prefix
        # too. Strip an optional "EC-" (any case) before parsing year/sequence.
        raw = q.removeprefix("EC-").removeprefix("ec-").strip()
        year, sep, seq = raw.partition("-")
        if year.isdigit():
            if sep and seq.isdigit():
                text |= Q(year=int(year), number_sequence=int(seq))
            elif not sep:
                text |= Q(year=int(year))
                text |= Q(number_sequence=int(year))
        queryset = queryset.filter(text)
    if status:
        queryset = queryset.filter(status=status)
    return queryset


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
    ec_qs = (
        EC.objects.filter(requester=user)
        .exclude(status=EC.Status.CANCELLED)
        .order_by("-year", "-number_sequence")
    )

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
    my_ecs = []
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
        
        version_list = [row["versions__version_number"] for row in versions]
        latest_comment = latest["versions__review__comment"] if versions else ""

        my_ecs.append({         
            "id": ec_id,
            "reference": data["reference"],
            "status": st,
            "versions_count": len(versions),
            "versions": version_list,
            "latest_comment": latest_comment,
        })

    return {
        "my_ecs": my_ecs,
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


DECISION_LABELS = {
    "approved": "Aprovado",
    "rejected": "Rejeitado",
}


def _display_name(user):
    if user is None:
        return None
    return user.full_name or user.username


def build_ec_timeline(ec) -> list[dict]:
    """Events (creation, version uploads, CD decisions) for one EC, oldest first.

    Derived from the models only — EC_DETAIL Decision 3. Reviews are reached
    through `version.review` (reverse one-to-one): `backlog` must not import
    `workflow` (ARCHITECTURE §5).
    """
    events = [
        {
            "title": "EC criada",
            "who": _display_name(ec.requester),
            "when": ec.created_at,
            "note": None,
        }
    ]
    for version in ec.versions.all():
        events.append(
            {
                "title": f"Documento {version.version_number} carregado",
                "who": _display_name(version.uploaded_by),
                "when": version.uploaded_at,
                "note": version.change_reason or None,
            }
        )
        try:
            review = version.review
        except ObjectDoesNotExist:
            continue
        decision_label = DECISION_LABELS.get(review.decision, review.get_decision_display())
        events.append(
            {
                "title": f"Decisão do CD: {decision_label}",
                "who": _display_name(review.cd),
                "when": review.decided_at,
                "note": review.comment or None,
            }
        )
    events.sort(key=lambda event: event["when"])
    return events


def cd_dashboard(user) -> dict:
    """Simplified CD-centric dashboard stats and queues."""
    ec_qs = EC.objects.filter(responsible_cd=user).exclude(status=EC.Status.CANCELLED)

    # 1. Status breakdown for doughnut chart
    status_counts = {row["status"]: row["n"] for row in ec_qs.values("status").annotate(n=Count("id"))}
    by_status = {value: status_counts.get(value, 0) for value, _label in EC.Status.choices if value != EC.Status.CANCELLED}

    # 2. Monthly creation for line/bar chart
    ec_by_month = [
        {"month": row["month"].strftime("%Y-%m"), "count": row["n"]}
        for row in ec_qs.exclude(creation_date=None)
            .annotate(month=TruncMonth("creation_date"))
            .values("month")
            .annotate(n=Count("id"))
            .order_by("month")
    ]

    # 3. Queues (Pending review & Rejected by me)
    pending_review = []
    rejected_by_me = []
    approved_by_me = []

    for ec in ec_qs.prefetch_related("versions__review"):
        latest = ec.versions.order_by("-id").first()
        if not latest:
            continue
        
        review = getattr(latest, "review", None)
        if review is None:
            pending_review.append({
                "id": ec.id,
                "reference": ec.reference,
                "version": latest.version_number,
                "uploaded_at": latest.uploaded_at,
            })
        elif review.decision == "approved" and review.cd_id == user.id:
            approved_by_me.append({
                "id": ec.id,
                "reference": ec.reference,
                "version": latest.version_number,
                "comment": review.comment,
                "decided_at": review.decided_at,
        })
        elif review.decision == "rejected" and review.cd_id == user.id:
            rejected_by_me.append({
                "id": ec.id,
                "reference": ec.reference,
                "version": latest.version_number,
                "comment": review.comment,
                "decided_at": review.decided_at,
            })

    return {
        "assigned_total": ec_qs.count(),
        "pending_total": len(pending_review),
        "approved_total": by_status.get(EC.Status.APPROVED, 0),
        "rejected_total": by_status.get(EC.Status.REJECTED, 0),
        "pending_review": pending_review,
        "rejected_by_me": rejected_by_me,
        "ec_by_status": by_status,
        "ec_by_month": ec_by_month,
    }


def des_team_dashboard(user) -> dict:
    """DES Team-centric dashboard stats and queues for ECs sent to DES."""
    ec_qs = EC.objects.filter(status=EC.Status.CLOSED).order_by("-year", "-number_sequence")

    return {
        "sent_total": ec_qs.count(),
        "sent_ecs": ec_qs,
    }


# --- Administrator dashboard: auditlog activity feed (PT labels) --------------
# The UI language is Portuguese, so an audit row is translated into one
# readable sentence such as "João Soares aprovou o EC 2026-012".
EC_STATUS_PT = {
    "in_validation": "Em validação",
    "approved": "Aprovada",
    "rejected": "Rejeitada",
    "sent_to_des": "Enviada para DES",
    "closed": "Fechada",
    "cancelled": "Cancelada",
}

_LOG_NOUN_PT = {
    "user": "o utilizador",
    "ec": "o EC",
    "release": "a Release",
}

_LOG_VERBS = {
    LogEntry.Action.CREATE: "criou",
    LogEntry.Action.UPDATE: "alterou",
    LogEntry.Action.DELETE: "removeu",
}

# `DocumentVersion.__str__` is "2026-012 - v1.0" and `Review.__str__` embeds it,
# so the EC code can be pulled back out of `object_repr`.
_EC_CODE_RE = re.compile(r"\d{4}-\d{3}")
_EC_VERSION_RE = re.compile(r"v\d+\.\d+")


def _changed(changes: dict, field: str):
    """Return `(old, new)` for `field`, or `(None, None)` if auditlog has none."""
    value = changes.get(field)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[0], value[1]
    return None, None


def _log_activity(entry: LogEntry) -> dict:
    """Turn one `LogEntry` row into a dict for the audit log table."""
    actor = entry.actor
    actor_name = (actor.full_name or actor.username) if actor else "Sistema"
    actor_role = actor.get_role_display() if actor and hasattr(actor, "get_role_display") else ""
    user_str = f"{actor_name} ({actor_role})" if actor_role else actor_name

    changes = entry.changes if isinstance(entry.changes, dict) else {}
    old_status, new_status = _changed(changes, "status")
    _, comment = _changed(changes, "comment")
    _, decision = _changed(changes, "decision")

    details_parts = []
    if decision:
        details_parts.append(f"Decisão: {decision}")
    if comment:
        details_parts.append(f"Comentário: {comment}")
    if old_status and new_status:
        old_pt = EC_STATUS_PT.get(old_status, old_status)
        new_pt = EC_STATUS_PT.get(new_status, new_status)
        details_parts.append(f"{old_pt} → {new_pt}")

    return {
        "timestamp": timezone.localtime(entry.timestamp).strftime("%d/%m/%Y %H:%M"),
        "actor": user_str,
        "action": entry.get_action_display(),
        "object": entry.object_repr,
        "details": " | ".join(details_parts),
    }



def admin_dashboard(user) -> dict:
    """Administrator dashboard: global counts + the recent activity feed.

    Every query for `Painel do Administrador` lives here so the view stays thin.
    """
    today = timezone.localdate()
    ec_qs = EC.objects.all()
    log_qs = LogEntry.objects.select_related("actor", "content_type")

    return {
        # KPI cards
        "users_total": User.objects.count(),
        "users_active": User.objects.filter(is_active=True).count(),
        "releases_total": Release.objects.count(),
        "releases_open": Release.objects.filter(is_open=True).count(),
        "ec_total": ec_qs.count(),
        "ec_pending_review": ec_qs.filter(status=EC.Status.IN_VALIDATION).count(),
        "actions_today": log_qs.filter(timestamp__date=today).count(),
        # "Atividade recente" panel
        "recent_logs": [
            _log_activity(entry) for entry in log_qs.order_by("-timestamp")[:5]
        ],
    }


def full_audit_log_entries():
    """Return structured EC and workflow lifecycle LogEntry rows for the full audit log table."""
    log_qs = (
        LogEntry.objects.select_related("actor", "content_type")
        .filter(content_type__model__in=["ec", "release", "review", "documentversion"])
        .order_by("-timestamp")
    )
    results = []
    for entry in log_qs:
        actor = entry.actor
        actor_name = (actor.full_name or actor.username) if actor else "Sistema"
        actor_role = actor.get_role_display() if actor and hasattr(actor, "get_role_display") else ""
        user_str = f"{actor_name} ({actor_role})" if actor_role else actor_name

        changes = entry.changes if isinstance(entry.changes, dict) else {}
        old_status, new_status = _changed(changes, "status")
        _, comment = _changed(changes, "comment")
        _, decision = _changed(changes, "decision")

        details_parts = []
        if decision:
            details_parts.append(f"Decisão: {decision}")
        if comment:
            details_parts.append(f"Comentário: {comment}")
        if old_status and new_status:
            old_pt = EC_STATUS_PT.get(old_status, old_status)
            new_pt = EC_STATUS_PT.get(new_status, new_status)
            details_parts.append(f"{old_pt} → {new_pt}")

        results.append({
            "timestamp": timezone.localtime(entry.timestamp).strftime("%d/%m/%Y %H:%M"),
            "actor": user_str,
            "action": entry.get_action_display(),
            "object": entry.object_repr,
            "details": " | ".join(details_parts),
        })
    return results
