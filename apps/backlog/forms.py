from django import forms

from apps.accounts.models import User

from .models import EC
from .selectors import open_releases_with_ec_count


class ReleaseChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.release_code} (aberta — {obj.ec_total}/{obj.capacity})"


class CDChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.full_name} ({obj.username})"


class ECCreateForm(forms.ModelForm):
    """EC_CREATE.md Decision 1: validation lives here, saving lives in the service."""

    class Meta:
        model = EC
        fields = ["reference", "description", "release", "responsible_cd"]
        widgets = {
            "reference": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "ex.: CR2026042"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Descreva a alteração técnica com clareza...",
                }
            ),
        }

    # The model allows null/blank (imported history has empty FKs), but a NEW
    # EC must have a release and a CD — required=True is the form's contract.
    release = ReleaseChoiceField(
        queryset=open_releases_with_ec_count(),
        required=True,
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    responsible_cd = CDChoiceField(
        queryset=User.objects.filter(role=User.Role.CD),
        label="Atribuir a CD",
        required=True,
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
