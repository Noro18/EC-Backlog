from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        REQUESTER = "requester", "Requester"
        CD = "cd", "CD"
        DES_TEAM = "des_team", "DES Team"
        ADMINISTRATOR = "administrator", "Administrator"

    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REQUESTER,
    )

    class Meta:
        db_table = "accounts_user"
        verbose_name = "User"
        verbose_name_plural = "Users"

    @property
    def full_name(self):
        return self.name or f"{self.first_name} {self.last_name}".strip()
