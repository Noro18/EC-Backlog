from django import forms

from apps.accounts.models import User

from .models import EC
from .selectors import open_releases_with_ec_count
from .services import NEW_RELEASE


class ReleaseChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.release_code} (aberta — {obj.ec_total}/{obj.capacity})"

    def to_python(self, value):
        # "+ Kria Release Foun" is not a Release row — let it through so
        # clean/validators see the sentinel instead of an invalid_choice.
        if value == NEW_RELEASE:
            return NEW_RELEASE
        return super().to_python(value)


class CDChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.full_name or obj.username


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Fresh open-Releases per form (never a stale shared queryset) plus
        # the on-demand option last (RF02). Plain list: no re-query on render.
        release_field = self.fields["release"]
        release_field.queryset = open_releases_with_ec_count()
        release_field.choices = [*release_field.choices, (NEW_RELEASE, "+ Kria Release Foun")]

    # Set by clean_release(); read by NewECView. ModelForm._post_clean assigns
    # every cleaned value onto the EC instance, so the sentinel string must
    # never survive in cleaned_data["release"] (FK rejects non-instances).
    wants_new_release = False

    def clean_release(self):
        value = self.cleaned_data.get("release")
        if value == NEW_RELEASE:
            self.wants_new_release = True
            return None
        return value

    responsible_cd = CDChoiceField(
        queryset=User.objects.filter(role=User.Role.CD),
        label="Atribuir a CD",
        required=True,
        empty_label=None,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    # Not an EC model field — the file becomes a DocumentVersion row, written by
    # documents.services.create_first_version (RF06). Optional (Assumption 6).
    # NO validators from apps.documents here: ARCHITECTURE.md forbids backlog.forms
    # importing documents — extension/size checks run inside the documents service.
    document = forms.FileField(
        label="Carregar Documento (.docx / .pdf)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".docx,.pdf"}),
    )
