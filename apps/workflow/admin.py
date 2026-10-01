from auditlog.registry import auditlog
from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        "document_version",
        "cd",
        "decision",
        "decided_at",
    ]
    list_filter = ["decision", "decided_at"]
    search_fields = ["cd__username", "document_version__ec__reference", "comment"]
    readonly_fields = ["decided_at", "created_at", "updated_at"]


auditlog.register(Review)
