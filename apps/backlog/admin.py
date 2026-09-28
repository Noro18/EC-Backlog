# Register your models here.
from django.contrib import admin
from . models import Release, EC


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ["release_id", "capacity", "is_open", "created", "updated"]
    readonly_fields = ["created", "updated"]


@admin.register(EC)
class ECAdmin(admin.ModelAdmin):
    list_display = ["ec_id", "status", "release", "requester", "cd", "created"]
    list_filter = ["status", "release", "created"]
    search_fields = ["ec_id", "release__release_id"]
    readonly_fields = ["created", "updated"]

from auditlog.registry import auditlog
auditlog.register(Release)
auditlog.register(EC)
