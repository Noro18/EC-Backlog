from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Extra Info", {"fields": ("name", "role")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Extra Info", {"fields": ("name", "role", "email")}),
    )
    list_display = ("username", "email", "name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")