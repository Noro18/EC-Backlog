from django.db import models

from apps.core.models import TimeStampedModel


class Release(TimeStampedModel):
    """A Release groups at most `capacity` ECs. Spec 4.3."""

    id = models.BigAutoField(primary_key=True)
    release_code = models.CharField(max_length=20, unique=True)
    year = models.PositiveSmallIntegerField()
    number_sequence = models.PositiveIntegerField()
    capacity = models.PositiveSmallIntegerField(default=10)
    is_open = models.BooleanField(default=True)
    production_go_live_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "backlog_release"
        ordering = ["-year", "-number_sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["year", "number_sequence"], name="release_year_number_uniq"
            )
        ]

    def __str__(self):
        return self.release_code

    @property
    def ec_count(self):
        return self.ecs.count()

    @property
    def status_label(self):
        """Read the annotation `ec_total` — requires `release_with_ec_count()`."""
        if self.ec_total >= self.capacity:
            return "Lotado"
        elif self.is_open:
            return "Aberta"
        else:
            return "Concluído"

    @property
    def is_full(self):
        return self.ec_count >= self.capacity


class EC(TimeStampedModel):
    """An Engineering Change. Spec 4.4.

    Identity is `year` + `number_sequence`; `ec_code` is computed, never stored.
    `is_imported` marks rows loaded from the historical Excel, which may leave
    requester, responsible_cd, creation_date and release empty.
    """

    class Status(models.TextChoices):
        IN_VALIDATION = "in_validation", "In Validation"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SENT_TO_DES = "sent_to_des", "Sent to DES"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.BigAutoField(primary_key=True)
    year = models.PositiveSmallIntegerField()
    number_sequence = models.PositiveIntegerField()
    reference = models.CharField(max_length=50)
    description = models.TextField()
    requester = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="requested_ecs",
        null=True,
        blank=True,
    )
    release = models.ForeignKey(
        "backlog.Release",
        on_delete=models.PROTECT,
        related_name="ecs",
        null=True,
        blank=True,
    )
    responsible_cd = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="assigned_ecs",
        null=True,
        blank=True,
    )
    creation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_VALIDATION)
    implemented_at = models.DateTimeField(null=True, blank=True)
    is_imported = models.BooleanField(default=False)

    class Meta:
        db_table = "backlog_ec"
        ordering = ["-year", "-number_sequence"]
        constraints = [
            models.UniqueConstraint(fields=["year", "number_sequence"], name="ec_year_number_uniq")
        ]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["creation_date"]),
        ]

    def __str__(self):
        return self.ec_code

    @property
    def ec_code(self):
        return f"{self.year}-{self.number_sequence:03d}"
