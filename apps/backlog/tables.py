import django_tables2 as tables

from .models import EC


class ECTable(tables.Table):
    action = tables.TemplateColumn(
        verbose_name="Ações",
        orderable=False,
        template_code="""
            <a href="{% url 'backlog:ec_detail' record.id %}"
                class="btn btn-sm btn-outline-info">
                <i class="bi bi-eye"></i> Ver
            </a>
        """,
    )
    class Meta:
        model = EC
        template_name = "django_tables2/bootstrap4.html"
        fields = ("id", "year", "number_sequence", "reference", "description", "requester", "responsible_cd", "creation_date", "release", "status", "is_imported", "action")