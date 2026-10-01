from auditlog.registry import auditlog
from django.contrib import admin

from .models import DocumentVersion


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = [
        "ec",
        "version_number",
        "uploaded_by",
        "uploaded_at",
        "change_reason",
    ]
    list_filter = ["version_number", "uploaded_at"]
    search_fields = ["ec__reference", "ec__year", "ec__number_sequence", "change_reason"]
    readonly_fields = ["uploaded_at", "created_at", "updated_at"]


auditlog.register(DocumentVersion)
