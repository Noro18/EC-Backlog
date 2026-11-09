import django_tables2 as tables

DOCUMENT_VERSION_ROW_MARKER = "data-version-row"


class DocumentVersionTable(tables.Table):
    """Read-only consultation table of document versions across all ECs."""

    ec = tables.TemplateColumn(
        verbose_name="EC / Referência",
        orderable=False,
        template_code=(
            '<a href="{% url \'backlog:ec_detail\' record.ec.pk %}" class="fw-semibold">'
            "EC-{{ record.ec.ec_code }}</a>"
            '<br><span class="text-muted small">{{ record.ec.reference }}</span>'
        ),
    )
    version = tables.TemplateColumn(
        verbose_name="Versão",
        orderable=False,
        template_code=(
            '<span class="badge text-bg-secondary">{{ record.version_number }}</span>'
        ),
    )
    uploaded_by = tables.TemplateColumn(
        verbose_name="Enviado por",
        orderable=False,
        template_code=(
            "{{ record.uploaded_by.full_name|default:record.uploaded_by.username }}"
        ),
    )
    uploaded_at = tables.TemplateColumn(
        verbose_name="Enviado em",
        orderable=False,
        attrs={"td": {"class": "text-nowrap text-muted small"}},
        template_code="{{ record.uploaded_at|date:'d/m/Y H:i' }}",
    )
    change_reason = tables.TemplateColumn(
        verbose_name="Motivo da alteração",
        orderable=False,
        template_code=(
            "{% if record.change_reason %}"
            "{{ record.change_reason|truncatechars:60 }}"
            "{% else %}—{% endif %}"
        ),
    )
    actions = tables.TemplateColumn(
        verbose_name="Documento",
        orderable=False,
        attrs={"td": {"class": "text-nowrap"}},
        template_code=(
            "{% with name=record.file.name|lower %}"
            '<span ' + DOCUMENT_VERSION_ROW_MARKER + '="{{ record.pk }}" class="d-none"></span>'
            "{% if not record.file %}"
            '<i class="bi bi-slash-circle text-muted" title="Sem ficheiro"></i>'
            "{% elif name|slice:'-5:' == '.docx' %}"
            '<i class="bi bi-file-earmark-word text-primary" title="Documento Word (DOCX)"></i>'
            "{% else %}"
            '<i class="bi bi-file-earmark-pdf text-danger" title="Documento PDF"></i>'
            "{% endif %}"
            " "
            '<button type="button" class="btn btn-sm btn-outline-primary" '
            'data-bs-toggle="modal" data-bs-target="#previewModal" '
            'data-preview-url="{% url \'documents:preview\' record.pk %}">'
            '<i class="bi bi-eye"></i> Pré-visualizar</button>'
            " "
            '<a href="{% url \'documents:download\' record.pk %}" '
            "class=\"btn btn-sm btn-outline-secondary\">"
            '<i class="bi bi-download"></i></a>'
            "{% endwith %}"
        ),
    )

    class Meta:
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle mb-0 small"}
        empty_text = "Ainda sem documentos."
