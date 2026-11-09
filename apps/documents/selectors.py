import re
from functools import reduce
from operator import or_

from django.db.models import Q

from apps.documents.models import DocumentVersion

#: EC codes are computed (`year` + `number_sequence`, shown as `EC-2026-014`),
#: not a stored field, so a code search is parsed into its parts here.
EC_CODE_PATTERN = re.compile(r"(?:EC-)?(\d{4})-(\d{1,4})", re.IGNORECASE)


def document_versions(q=None):
    """All document versions across every EC, newest upload first (RF05).

    Administrator-only consultation read; filtering matches the EC-list
    search style (EC code, reference, version number).
    """

    queryset = (
        DocumentVersion.objects.select_related("ec", "uploaded_by")
        .order_by("-uploaded_at", "-id")
    )
    if not q:
        return queryset

    conditions = [Q(ec__reference__icontains=q), Q(version_number__icontains=q)]
    code_match = EC_CODE_PATTERN.fullmatch(q.strip())
    if code_match:
        conditions.append(
            Q(ec__year=int(code_match.group(1)))
            & Q(ec__number_sequence=int(code_match.group(2)))
        )
    combined = reduce(or_, conditions)
    return queryset.filter(combined)
