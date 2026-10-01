from django_tables2 import tables

from .models import EC


class ECTable(tables.Table):
    class Meta:
        model = EC
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "year", "number_sequence", "reference", "description", "requester", "responsible_cd", "creation_date", "release", "status", "is_imported")