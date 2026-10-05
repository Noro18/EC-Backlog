def next_ec_number(year: int) -> int:
    """Return the next EC number for a given year."""
    from apps.backlog.models import EC

    last_ec = EC.objects.filter(year=year).order_by("-number_sequence").first()
    if last_ec is None:
        return 1
    return last_ec.number_sequence + 1