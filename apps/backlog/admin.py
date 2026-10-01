# Register your models here.
from django.contrib import admin

from .models import EC, Release


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


from auditlog.registry import auditlog

auditlog.register(Release)
auditlog.register(EC)
