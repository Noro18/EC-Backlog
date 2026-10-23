from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class UserCreateForm(UserCreationForm):
    """USER_CREATE.md: Portuguese labels; `role` and `name` are required.

    Validation lives here; the row is written by services.create_user.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "name", "email", "role", "is_active")
        labels = {
            "username": "Nome de utilizador",
            "name": "Nome",
            "email": "Email",
            "role": "Perfil",
            "is_active": "Estado",
        }

        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "ex.: maria.gusmao",
                    "autocomplete": "off",
                }
            ),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "ex.: Maria da Costa"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "ex.: maria@example.com"}
            ),
            "role": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Decision 7: the model allows blank names (imported history), a user
        # created here must have one — same contract as ECCreateForm's required FKs.
        self.fields["name"].required = True
        # The two fields UserCreationForm brings along: our labels, our
        # Bootstrap classes, our short help text.
        self.fields["password1"].label = "Palavra-passe"
        self.fields["password1"].widget.attrs.update({"class": "form-control"})
        self.fields["password1"].help_text = "Mínimo de 8 caracteres."
        self.fields["password2"].label = "Confirmar palavra-passe"
        self.fields["password2"].widget.attrs.update({"class": "form-control"})
        self.fields["password2"].help_text = ""