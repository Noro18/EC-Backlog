import django_tables2 as tables
from django.utils.html import format_html

from .models import EC, Release

STATUS_BADGE_CLASSES = {
    "in_validation": "text-bg-warning",
    "approved": "text-bg-success",
    "rejected": "text-bg-danger",
    "sent_to_des": "text-bg-info",
    "closed": "text-bg-secondary",
    "cancelled": "text-bg-dark",
}

RELEASE_BADGE_CLASSES = {
    "Lotado": "text-bg-danger",
    "Aberta": "text-bg-warning",
    "Concluído": "text-bg-success",
}


class ReleaseTable(tables.Table):
    release_code = tables.TemplateColumn(
        verbose_name="Release",
        orderable=False,
        template_code="""<a href="{% url 'backlog:release_detail' record.id %}" class="fw-semibold text-decoration-none">{{ record.release_code }}</a>""",
    )
    year = tables.Column(attrs={"td": {"class": "text-nowrap"}})
    number_sequence = tables.Column(verbose_name="Seq.", attrs={"td": {"class": "text-nowrap"}})
    ec_total = tables.TemplateColumn(
        verbose_name="ECs",
        attrs={"td": {"class": "text-nowrap"}},
        template_code="{{ record.ec_total }} / {{record.capacity}}",
    )
    status = tables.Column(
        verbose_name="Status",
        orderable=False,
        empty_values=(),
        attrs={"th": {"class": "text-center"}},
    )

    def render_status(self, record):
        return format_html(
            '<span class="badge {}">{}</span>',
            RELEASE_BADGE_CLASSES[record.status_label],
            record.status_label,
        )

    action = tables.TemplateColumn(
        verbose_name="Ações",
        orderable=False,
        empty_values=(),
        template_code="""
            <a href="{% url 'backlog:release_detail' record.id %}"
                class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-eye"></i> Ver
            </a>
        """,
    )

    class Meta:
        model = Release
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "release_code",
            "year",
            "number_sequence",
            "ec_total",
            "status",
            "action",
        )
        attrs = {"class": "table table-sm table-hover align-middle mb-0"}
        empty_text = "Nenhuma Release encontrada."
        per_page = 25
        order_by = ("-year", "-number_sequence")


class ECTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="EC",
        orderable=False,
        template_code="""<span class="fw-semibold">{{ record.ec_code }}</span>""",
    )
    reference = tables.Column(
        verbose_name="Referência",
        attrs={"td": {"class": "text-nowrap text-body-secondary"}},
    )
    description = tables.Column(
        verbose_name="Descrição",
        attrs={"td": {"class": "text-body-secondary text-truncate", "style": "max-width: 28rem;"}},
    )
    release = tables.Column(attrs={"td": {"class": "text-nowrap"}})
    requester = tables.Column(attrs={"td": {"class": "text-nowrap"}})
    responsible_cd = tables.Column(verbose_name="CD", attrs={"td": {"class": "text-nowrap"}})
    creation_date = tables.Column(
        verbose_name="Criado em",
        attrs={"td": {"class": "text-nowrap font-monospace text-body-secondary"}},
    )
    
    status = tables.Column(verbose_name="Status", attrs={"th": {"class": "text-center"}})
    is_imported = tables.TemplateColumn(
        verbose_name="Origem",
        orderable=False,
        empty_values=(),
        template_code="""
            {% if record.is_imported %}
                <span class="badge text-bg-light border text-body-secondary">Importado</span>
            {% else %}
                <span class="text-body-tertiary">Manual</span>
            {% endif %}
        """,
    )
    action = tables.TemplateColumn(
        verbose_name="Ações",
        orderable=False,
        empty_values=(),
        template_code="""
            <a href="{% url 'backlog:ec_detail' record.id %}"
                class="btn btn-sm btn-outline-secondary">
                <i class="bi bi-eye"></i> Ver
            </a>
        """,
    )

    def render_status(self, record):
        badge_class = STATUS_BADGE_CLASSES.get(record.status, "text-bg-secondary")
        return format_html('<span class="badge {}">{}</span>', badge_class, record.status_label())

    class Meta:
        model = EC
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "ec_code",
            "reference",
            "description",
            "release",
            "requester",
            "responsible_cd",
            "creation_date",
            "status",
            "is_imported",
            "action",
        )
        attrs = {"class": "table table-sm table-hover align-middle mb-0"}
        empty_text = "Nenhuma EC encontrada."
        per_page = 25
        order_by = ("-year", "-number_sequence")
