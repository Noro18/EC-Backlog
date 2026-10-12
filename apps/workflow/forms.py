from django import forms


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
