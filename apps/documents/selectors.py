import re
from functools import reduce
from operator import or_

from django.db.models import Count, Max, Q

from apps.documents.models import DocumentVersion

#: EC codes are computed (`year` + `number_sequence`, shown as `EC-2026-014`),
#: not a stored field, so a code search is parsed into its parts here.
EC_CODE_PATTERN = re.compile(r"(?:EC-)?(\d{4})-(\d{1,4})", re.IGNORECASE)


def ec_versions(ec_pk):
    """All document versions of one EC, newest first (RF05).

    The gallery query: one card per version, latest upload at the top.
    """

    return (
        DocumentVersion.objects.select_related("ec", "uploaded_by")
        .filter(ec_id=ec_pk)
        .order_by("-uploaded_at", "-id")
    )


def version_ecs(q=None):
    """ECs that own at least one document version (RF05).

    The chips page query: one row per EC with its version count and newest
    upload time, ECs sorted by that newest upload so recently active
    documents surface first. The optional `q` narrows the chips by EC
    reference or EC code (`EC-<year>-<nnn>`, parsed because `ec_code` is a
    computed property, not a stored column).

    Returns dictionaries with `ec_id`, `ec__reference`, `ec__year`,
    `ec__number_sequence`, `version_count`, and `latest_upload`.
    """

    filter_conditions = []
    if q:
        filter_conditions.append(Q(ec__reference__icontains=q))
        code_match = EC_CODE_PATTERN.fullmatch(q.strip())
        if code_match:
            filter_conditions.append(
                Q(ec__year=int(code_match.group(1)))
                & Q(ec__number_sequence=int(code_match.group(2)))
            )

    queryset = DocumentVersion.objects.all()
    if filter_conditions:
        queryset = queryset.filter(reduce(or_, filter_conditions))

    return (
        queryset.values("ec_id", "ec__reference", "ec__year", "ec__number_sequence")
        .annotate(version_count=Count("id"), latest_upload=Max("uploaded_at"))
        .order_by("-latest_upload", "-ec_id")
    )
