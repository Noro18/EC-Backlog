from django import forms

from apps.accounts.models import User  # workflow → accounts: downward, allowed


class CDChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.full_name} ({obj.username})"


class ReviewForm(forms.Form):
    """RF09 decision form: approve/reject radio + comment.

    Comment is required only for rejection — enforced here (UX) and again in
    the service + DB constraint (API safety + last resort).
    """

    DECISION_CHOICES = [
        ("approve", "Aprovar"),
        ("reject", "Rejeitar"),
    ]

    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect,
        label="Decisão",
    )
    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Obrigatório em caso de rejeição — o solicitante vai ler isto.",
            }
        ),
        required=False,
        label="Comentário",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == "reject" and not (cleaned.get("comment") or "").strip():
            raise forms.ValidationError(
                {"comment": ["O comentário é obrigatório para rejeitar a EC."]}
            )
        return cleaned


class ResubmitForm(forms.Form):
    """RF05 resubmit form: new file + what-changed reason, optional
    major-bump tickbox and CD reassignment."""

    document = forms.FileField(
        label="Novo documento (.docx / .pdf)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
    change_reason = forms.CharField(
        label="O que mudou?",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Ex.: adicionado o diagrama unifilar que faltava",
            }
        ),
    )
    major_change = forms.BooleanField(
        label="Mudança grande (nova versão vX.0 em vez de vX.Y)",
        required=False,
    )
    responsible_cd = CDChoiceField(
        queryset=User.objects.filter(role=User.Role.CD),
        label="Manter ou trocar o CD",
        required=False,
        empty_label="Manter o CD atual",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean_change_reason(self):
        reason = (self.cleaned_data.get("change_reason") or "").strip()
        if not reason:
            raise forms.ValidationError("Descreva o que mudou nesta versão.")
        return reason
