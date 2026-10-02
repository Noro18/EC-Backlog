from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Create a user with the Administrator role and Django admin access."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--name", default="", help="Display name.")
        parser.add_argument(
            "--email",
            default="",
            help="Unique email. Defaults to <username>@localhost if omitted.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        username = options["username"].strip()

        if not username:
            raise CommandError("Username cannot be empty.")

        if user_model.objects.filter(username=username).exists():
            raise CommandError(f'Username "{username}" is already taken.')

        email = options["email"].strip() or f"{username}@localhost"
        if user_model.objects.filter(email=email).exists():
            raise CommandError(f'Email "{email}" is already taken.')

        password = self._prompt_password()
        try:
            validate_password(password, user_model(username=username, email=email))
        except ValidationError as exc:
            raise CommandError("\n".join(exc.messages)) from exc

        user_model.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            name=options["name"].strip(),
            role=user_model.Role.ADMINISTRATOR,
        )

        self.stdout.write(
            self.style.SUCCESS(f'Administrator "{username}" created with role=administrator.')
        )
        self.stdout.write("Sign in at /admin/ with this username and password.")

    def _prompt_password(self):
        password = self._secret("Password: ")
        confirmation = self._secret("Password (again): ")

        if password != confirmation:
            raise CommandError("Passwords do not match.")

        if not password:
            raise CommandError("Password cannot be empty.")

        return password

    def _secret(self, prompt):
        from getpass import getpass

        return getpass(prompt=f"  {prompt}")
