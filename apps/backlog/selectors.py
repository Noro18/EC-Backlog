from django.db.models import Count

from apps.backlog.models import Release


def release_with_ec_count():
    """Return a queryset of releases annotated with the number of ECs."""
    return Release.objects.annotate(ec_total=Count("ecs")).order_by("-year", "-number_sequence")
