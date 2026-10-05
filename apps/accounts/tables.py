import django_tables2 as tables
from django.utils.html import format_html

from .models import User

ROLE_BADGE_CLASSES = {
    "requester": "text-bg-info",
    "cd": "text-bg-warning",
    "des_team": "text-bg-success",
    "administrator": "text-bg-danger"
}

class UserTable(tables.Table):
    name = tables.Column(verbose_name="Nome")
    username = tables.Column(verbose_name="Utilizador")
    email = tables.Column(verbose_name="Email")
    role = tables.Column(verbose_name="Role", empty_values=())
    is_active = tables.Column(verbose_name="Estado", empty_values=())
    last_login = tables.Column(verbose_name="Última atividade")

    def render_name(self, record):
        return record.full_name or record.username
    
    def render_role(self, record):
        badge = ROLE_BADGE_CLASSES.get(record.role, "text-bg-secondary")
        return format_html(
            '<span class="badge {}">{}</span>', badge, record.get_role_display()
        )
    
    def render_is_active(self, record):
        if record.is_active:
            return format_html('<span class="badge {}">Ativo</span>', "text-bg-success")
        return format_html('<span class="badge {}">Inativo</span>', "text-bg-secondary")

    def render_last_login(self, record):
        if record.last_login is None:
            return format_html('<span class="{}">—</span>', "text-bg-tertiary")
        return record.last_login.strftime("%d/%m/%Y %H:%M")

    class Meta:
        model = User
        fields = ("name", "username", "email", "role", "is_active", "last_login")
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-sm table-hover align-middle mb-0"}
        empty_text = "Nenhum utilizador encontrado."
        per_page = 25
        order_by = "username"

    
    
