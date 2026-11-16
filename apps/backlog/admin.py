# Register your models here.
from auditlog.models import LogEntry
from auditlog.registry import auditlog
from django.contrib import admin
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import EC, Release
from .selectors import EC_STATUS_PT


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = [
        "release_code",
        "year",
        "number_sequence",
        "capacity",
        "is_open",
        "production_go_live_date",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_open", "year"]
    search_fields = ["release_code"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(EC)
class ECAdmin(admin.ModelAdmin):
    list_display = [
        "ec_code",
        "reference",
        "status",
        "release",
        "requester",
        "responsible_cd",
        "creation_date",
        "is_imported",
    ]
    list_filter = ["status", "is_imported", "year", "release", "creation_date"]
    search_fields = ["reference", "description", "year", "number_sequence"]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(description="EC ID", ordering=("year", "number_sequence"))
    def ec_code(self, obj):
        return obj.ec_code


auditlog.register(Release, exclude_fields=["created_at", "updated_at"])
auditlog.register(EC, exclude_fields=["created_at", "updated_at"])

admin.site.unregister(LogEntry)


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Read-only audit trail: human-readable columns, no noise (RNF02)."""

    list_display = ["created", "actor_name", "action_badge", "object_link", "changes_summary"]
    list_filter = ["action", ("content_type", admin.RelatedOnlyFieldListFilter), "timestamp"]
    search_fields = ["actor__username", "actor__first_name", "actor__last_name", "object_repr"]
    date_hierarchy = "timestamp"
    list_select_related = ["actor", "content_type"]
    ordering = ["-timestamp"]

    # Inline colours: the admin does not load static/css/app.css (.badge.bg-* scoped there).
    _BADGE_COLORS = {
        LogEntry.Action.CREATE: ("Dibuat", "#198754"),
        LogEntry.Action.UPDATE: ("Diperbarui", "#0d6efd"),
        LogEntry.Action.DELETE: ("Dihapus", "#dc3545"),
    }
    _OBJECT_LABELS = {
        "ec": "EC",
        "user": "User",
        "release": "Release",
        "review": "Review",
        "documentversion": "Document version",
    }
    _SUMMARY_LIMIT = 200

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Created", ordering="timestamp")
    def created(self, obj):
        return timezone.localtime(obj.timestamp).strftime("%d-%b-%Y %H:%M")

    # Named `actor_name`, not `actor`: a ModelAdmin method loses to the model
    # field of the same name in django.contrib.admin.utils.lookup_field.
    @admin.display(description="Actor", ordering="actor__username")
    def actor_name(self, obj):
        if obj.actor_id is None:
            return "Sistema"
        actor = obj.actor
        return actor.full_name or actor.username

    @admin.display(description="Aksi")
    def action_badge(self, obj):
        label, color = self._BADGE_COLORS.get(obj.action, (obj.get_action_display(), "#6c757d"))
        return format_html(
            '<span style="background-color:{};color:#fff;padding:1px 7px;border-radius:4px;">{}</span>',
            color,
            label,
        )

    @admin.display(description="Objek")
    def object_link(self, obj):
        text = obj.object_repr
        if obj.content_type_id is None:
            return text
        content_type = obj.content_type
        label = self._OBJECT_LABELS.get(content_type.model, content_type.model.capitalize())
        if not text.startswith(label):
            text = f"{label} {text}"
        try:
            url = reverse(
                f"admin:{content_type.app_label}_{content_type.model}_change",
                args=[obj.object_pk],
            )
        except NoReverseMatch:
            return text
        return format_html('<a href="{}">{}</a>', url, text)

    @admin.display(description="Perubahan")
    def changes_summary(self, obj):
        parts = []
        for field, values in obj.changes_dict.items():
            if field == "id" or not isinstance(values, (list, tuple)) or len(values) != 2:
                continue
            old, new = values
            if self._is_empty(old) and self._is_empty(new):
                continue
            if field == "comment":
                if self._is_empty(old):
                    parts.append("comment: (baru diisi)")
                    continue
                if self._is_empty(new):
                    parts.append("comment: (dihapus)")
                    continue
            parts.append(self._format_change(field, old, new))
        if not parts:
            return "-"
        summary = "; ".join(parts)
        if len(summary) > self._SUMMARY_LIMIT:
            summary = summary[: self._SUMMARY_LIMIT - 1].rstrip() + "…"
        return summary

    @staticmethod
    def _is_empty(value):
        # auditlog stringifies before persisting, so `None` arrives back as "None".
        return value is None or value == "" or value == "None"

    @classmethod
    def _format_change(cls, field, old, new):
        if field == "status":
            old = EC_STATUS_PT.get(old, old)
            new = EC_STATUS_PT.get(new, new)
        old_text = "" if cls._is_empty(old) else str(old)
        new_text = "" if cls._is_empty(new) else str(new)
        if not old_text:
            return f"{field}: {new_text}".rstrip()
        return f"{field}: {old_text} → {new_text}".rstrip()
