from django.db.models import Count, F

from apps.backlog.models import Release


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
