"""Self-service profile tests — spec `.opencode/specs/PROFILE_SELF_EDIT.md`.

Same module-level `pytestmark` and `class Test...:` style as
`apps/accounts/tests/test_views.py`.
"""

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse

from apps.backlog.tests.factories import UserFactory

User = get_user_model()

PASSWORD = "SenhaForte123!"
NEW_PASSWORD = "NovaSenhaForte456!"

pytestmark = pytest.mark.django_db


def profile_url():
    return reverse("accounts:profile")


def seeded_user(role="requester", username="maria.gusmao", email="maria@example.com"):
    """A user whose password is really set (factories do not hash it)."""

    user = UserFactory(role=role, username=username, email=email)
    user.set_password(PASSWORD)
    user.save()
    return user


def login_with(client, user):
    client.force_login(user)
    return user


class TestProfileAccess:
    def test_anonymous_redirects_to_login(self, client):
        response = client.get(profile_url())

        assert response.status_code == 302
        assert "?next=" in response.url

    @pytest.mark.parametrize("role", ["requester", "cd", "des_team", "administrator"])
    def test_every_role_reaches_the_page(self, client, role):
        login_with(client, seeded_user(role=role))

        response = client.get(profile_url())

        assert response.status_code == 200
        assert "Meu Perfil" in response.content.decode()

    def test_navbar_person_icon_links_to_the_profile(self, client):
        login_with(client, seeded_user())

        html = client.get(profile_url()).content.decode()

        assert profile_url() in html
        assert 'title="perfil"' in html


class TestProfileData:
    def test_shows_username_and_role_read_only(self, client):
        user = login_with(client, seeded_user(username="maria.gusmao"))

        html = client.get(profile_url()).content.decode()

        assert "maria.gusmao" in html
        assert user.get_role_display() in html

    def test_username_note_points_to_the_administrator(self, client):
        login_with(client, seeded_user())

        html = client.get(profile_url()).content.decode()

        assert "A alteração do nome de utilizador é feita pelo Administrador." in html

    def test_name_and_email_update_persists(self, client):
        user = login_with(client, seeded_user())

        response = client.post(
            profile_url(),
            {"form": "pessoa", "name": "Maria da Costa", "email": "maria.costa@example.com"},
            follow=True,
        )

        html = response.content.decode()
        user.refresh_from_db()

        assert "Dados atualizados com sucesso." in html
        assert user.name == "Maria da Costa"
        assert user.email == "maria.costa@example.com"
        assert "Maria da Costa" in html  # navbar identity line follows the edit

    def test_duplicate_email_rejected_in_portuguese(self, client):
        login_with(client, seeded_user(username="maria.gusmao"))
        UserFactory(username="joao.silva", email="joao@example.com")

        response = client.post(
            profile_url(),
            {"form": "pessoa", "name": "Maria", "email": "joao@example.com"},
            follow=True,
        )

        html = response.content.decode()
        user = User.objects.get(username="maria.gusmao")

        assert "Este email já está em uso." in html
        assert user.email == "maria@example.com"

    def test_blank_name_rejected(self, client):
        user = login_with(client, seeded_user())

        client.post(profile_url(), {"form": "pessoa", "name": "", "email": user.email})

        user.refresh_from_db()
        assert user.name == ""  # factory leaves name blank; nothing changed

    def test_extra_fields_cannot_change_username_or_role(self, client):
        user = login_with(client, seeded_user(username="maria.gusmao"))

        client.post(
            profile_url(),
            {
                "form": "pessoa",
                "name": "Maria",
                "email": user.email,
                "username": "hacker",
                "role": "administrator",
            },
        )

        user.refresh_from_db()
        assert user.username == "maria.gusmao"
        assert user.role == "requester"


class TestChangePassword:
    def post_senha(self, client, old, new, confirm=None):
        return client.post(
            profile_url(),
            {
                "form": "senha",
                "old_password": old,
                "new_password1": new,
                "new_password2": confirm if confirm is not None else new,
            },
            follow=True,
        )

    def test_password_change_succeeds(self, client):
        user = login_with(client, seeded_user())

        response = self.post_senha(client, PASSWORD, NEW_PASSWORD)

        html = response.content.decode()
        user.refresh_from_db()

        assert "Palavra-passe alterada com sucesso." in html
        assert authenticate(username=user.username, password=NEW_PASSWORD)
        assert not authenticate(username=user.username, password=PASSWORD)

    def test_session_survives_the_change(self, client):
        login_with(client, seeded_user())

        self.post_senha(client, PASSWORD, NEW_PASSWORD)

        assert client.get(profile_url()).status_code == 200

    def test_wrong_current_password_rejected_in_portuguese(self, client):
        user = login_with(client, seeded_user())

        response = self.post_senha(client, "SenhaErrada999!", NEW_PASSWORD)

        html = response.content.decode()

        assert "incorreta" in html
        assert not authenticate(username=user.username, password=NEW_PASSWORD)

    def test_weak_password_rejected(self, client):
        user = login_with(client, seeded_user())

        response = self.post_senha(client, PASSWORD, "123")

        html = response.content.decode()

        assert "Nova palavra-passe" in html  # the error lands on the password field
        assert not authenticate(username=user.username, password="123")

    def test_mismatched_confirmation_rejected(self, client):
        user = login_with(client, seeded_user())

        response = self.post_senha(
            client, PASSWORD, NEW_PASSWORD, confirm="OutraSenha789!"
        )

        html = response.content.decode()

        assert "incorreta" not in html  # the old password was right
        assert not authenticate(username=user.username, password=NEW_PASSWORD)
