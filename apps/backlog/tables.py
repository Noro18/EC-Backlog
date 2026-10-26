import django_tables2 as tables
from django.utils.html import format_html

from .models import EC, Release

EC_BADGE_CLASSES = {
    "in_validation": "text-bg-warning",
    "approved": "text-bg-success",
    "rejected": "text-bg-danger",
    "sent_to_des": "text-bg-info",
    "closed": "text-bg-secondary",
    "cancelled": "text-bg-dark",
}

RELEASE_BADGE_CLASSES = {
    "Lotado": "text-bg-danger",
    "Aberta": "text-bg-success",
    "Concluído": "text-bg-secondary",
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

    class Meta:
        model = Release
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "release_code",
            "year",
            "number_sequence",
            "ec_total",
            "status",
        )
        attrs = {"class": "table table-sm table-hover align-middle mb-0"}
        empty_text = "Nenhuma Release encontrada."
        per_page = 25
        order_by = ("-year", "-number_sequence")


class ECTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="EC",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="fw-semibold text-decoration-none">EC-{{ record.ec_code }}</a>""",
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
    def render_status(self, record):
        badge_class = EC_BADGE_CLASSES.get(record.status, "text-bg-secondary")
        return format_html(
            '<span class="badge {}">{}</span>', badge_class, record.get_status_display()
        )

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
        )
        attrs = {"class": "table table-sm table-hover align-middle mb-0"}
        empty_text = "Nenhuma EC encontrada."
        per_page = 25
        order_by = ("-year", "-number_sequence")

class ECDesTeamTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="EC",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="fw-semibold text-decoration-none">EC-{{ record.ec_code }}</a>""",
    )
    reference = tables.Column(
        verbose_name="Referência",
        attrs={"td": {"class": "text-nowrap text-body-secondary"}},
    )
    description = tables.Column(
        verbose_name="Descrição",
        attrs={"td": {"class": "text-body-secondary text-truncate", "style": "max-width: 28rem;"}},
    )
    requester = tables.Column(attrs={"td": {"class": "text-nowrap"}})
    actions = tables.TemplateColumn(
        verbose_name="Ações",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="btn btn-sm btn-outline-primary">Ver Detalhes</a>""",
        attrs={"th": {"class": "text-end"}, "td": {"class": "text-end"}},
    )

    class Meta:
        model = EC
        template_name = "django_tables2/bootstrap5.html"
        fields = ("ec_code", "reference", "description", "requester", "actions")
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Nenhum EC enviado para a DES no momento."


class ECRequesterTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="Referencia",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="text-decoration-none">{{ record.reference }}</a>""",
    )
    versions = tables.TemplateColumn(
        verbose_name="Versões",
        orderable=False,
        template_code="""
            <div class="d-flex align-items-center gap-1">
                {% for v in record.versions %}
                    {% if not forloop.first %}<span class="text-muted small">→</span>{% endif %}
                    <span class="badge {% if forloop.last %}text-bg-dark{% else %}text-bg-light border text-body-secondary{% endif %} px-2 py-1">
                        {{ v }}
                    </span>
                {% empty %}
                    <span class="text-muted small">Sem versões</span>
                {% endfor %}
            </div>
        """,
    )
    status = tables.TemplateColumn(
        verbose_name="Estado",
        orderable=False,
        template_code="""
            {% if record.status == "approved" %}
                <span class="badge text-bg-success">Aprovado</span>
            {% elif record.status == "rejected" %}
                <span class="badge text-bg-danger">Rejeitado</span>
            {% elif record.status == "in_validation" %}
                <span class="badge text-bg-warning text-dark">Em Validação</span>
            {% elif record.status == "sent_to_des" %}
                <span class="badge text-bg-info">Enviada para DES</span>
            {% else %}
                <span class="badge text-bg-secondary">{{ record.status }}</span>
            {% endif %}
        """,
    )
    latest_comment = tables.TemplateColumn(
        verbose_name="Comentário do CD",
        orderable=False,
        template_code="""<span class="text-body-secondary small text-truncate d-inline-block" style="max-width: 18rem;">{{ record.latest_comment|default:"Sem comentários." }}</span>""",
    )

    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        fields = ("ec_code", "versions", "status", "latest_comment")
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Nenhuma EC encontrada."


class CDPendingReviewTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="Referencia",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="text-decoration-none">{{ record.reference }}</a>""",
    )
    versions = tables.TemplateColumn(
        verbose_name="Versões",
        orderable=False,
        template_code="""
            <div class="d-flex align-items-center gap-1">
                {% for v in record.versions %}
                    {% if not forloop.first %}<span class="text-muted small">→</span>{% endif %}
                    <span class="badge {% if forloop.last %}text-bg-dark{% else %}text-bg-light border text-body-secondary{% endif %} px-2 py-1">
                        {{ v }}
                    </span>
                {% empty %}
                    <span class="text-muted small">Sem versões</span>
                {% endfor %}
            </div>
        """,
    )

    uploaded_at = tables.TemplateColumn(
        verbose_name="Enviado em",
        orderable=False,
        template_code="""<small class="text-muted">{{ record.uploaded_at|date:"d/m/Y H:i" }}</small>""",
    )


    actions = tables.TemplateColumn(
        verbose_name="Ações",
        orderable=False,
        template_code="""<a href="{% url 'backlog:ec_detail' record.id %}" class="btn btn-sm btn-outline-primary">Ver Detalhes</a>""",
        attrs={"th": {"class": "text-end"}, "td": {"class": "text-end"}},
    )
    
    class Meta:
        fields = ("ec_code", "versions", "uploaded_at", "actions") 
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Nenhum EC pendente de revisão."


class ActivityTable(tables.Table):
    """`Atividade recente` rows on the admin dashboard.

    Records are the `{time, description}` dicts built by `admin_dashboard`,
    not `LogEntry` rows, so both columns are plain and not orderable.
    """

    time = tables.Column(
        verbose_name="Hora",
        orderable=False,
        attrs={"td": {"class": "text-muted small text-nowrap", "style": "width: 5.5rem;"}},
    )
    description = tables.Column(
        verbose_name="Atividade",
        orderable=False,
        attrs={"td": {"class": "small"}},
    )

    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Sem atividade registada."

class FullAuditLogTable(tables.Table):
    """Professional enterprise audit log table."""

    timestamp = tables.Column(verbose_name="Hora", orderable=False, attrs={"td": {"class": "text-nowrout text-muted small"}})
    actor = tables.Column(verbose_name="Utilizador (Role)", orderable=False)
    action = tables.Column(verbose_name="Ação", orderable=False)
    object = tables.Column(verbose_name="Objeto", orderable=False)
    details = tables.Column(verbose_name="Detalhes / Status", orderable=False)

    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle mb-0 small"}
        empty_text = "Sem registos de auditoria."


class PendingECTable(tables.Table):
    ec_code = tables.TemplateColumn(
        verbose_name="EC / Referência",
        orderable=False,
        template_code="""
            <div>
                <a href="{% url 'backlog:ec_detail' record.id %}"
                   class="fw-semibold text-decoration-none">
                    {{ record.ec_code }}
                </a>
                <div class="text-muted small">{{ record.reference }}</div>
            </div>
        """,
    )
    requester = tables.Column(
        verbose_name="Solicitante",
        orderable=False,
    )
    responsible_cd = tables.Column(
        verbose_name="CD responsável",
        orderable=False,
    )
    version = tables.Column(
        verbose_name="Versão",
        orderable=False,
    )
    uploaded_at = tables.DateTimeColumn(
        verbose_name="Enviado em",
        format="d/m/Y H:i",
        orderable=False,
    )
    action = tables.TemplateColumn(
        verbose_name="Ação",
        orderable=False,
        template_code="""
            <a href="{% url 'backlog:ec_detail' record.id %}"
               class="btn btn-sm btn-outline-primary">
                Ver detalhe
            </a>
        """,
        attrs={"th": {"class": "text-end"}, "td": {"class": "text-end"}},
    )

    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        fields = (
            "ec_code",
            "requester",
            "responsible_cd",
            "version",
            "uploaded_at",
            "action",
        )
        attrs = {"class": "table table-hover align-middle mb-0"}
        empty_text = "Nenhum EC pendente de revisão."
