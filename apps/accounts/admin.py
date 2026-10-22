from auditlog.registry import auditlog
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm

from .models import User


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "name", "role", "email")


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm

    fieldsets = UserAdmin.fieldsets + (
        ("Extra Info", {"fields": ("name", "role")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),
        }),
        ("Extra Info", {"fields": ("name", "role", "email")}),
    )
list_display = ("username", "email", "name", "rcole", "is_staff", "is_active")
list_filter = ("role", "is_staff", "is_active")


# RNF02: user creations/edits must show up in the audit feed that feeds the
# administrator dashboard's "Ações hoje" and "Atividade recente" widgets.
auditlog.register(User)