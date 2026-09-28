# Create your models here.

from django.db import models
from apps.core.models import TimeStampedModel


class Release(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    release_id = models.CharField(max_length=20)
    capacity = models.IntegerField(default=10)
    is_open = models.BooleanField(default=True)

    class Meta:
        db_table = "backlog_release"
        ordering = ["-release_id"] # Newest release first, bele overwite iha vieews
    
    def __str__(self):
        return self.release_id

    @property
    def ec_count(self):
        return self.ecs.count()

    @property
    def is_full(self):
        return self.ec_count >= self.capacity

class EC(TimeStampedModel):
    class Status(models.TextChoices):
        IN_VALIDATION = "in_validation", "In Validation"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SENT_TO_DES = "sent_to_des", "Sent to DES"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"
    
    ec_id = models.CharField(max_length=20, unique=True)
    status =models.CharField(max_length=20, choices=Status.choices, default=Status.IN_VALIDATION)
    release = models.ForeignKey(
        "Release", 
        on_delete=models.PROTECT,
        related_name="ecs"
    )
    requester = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="ecs_created"
    )
    cd = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="ecs_assigned",
        null=True,
        blank=True
    )

    class Meta:
        db_table = "backlog_ec"
        ordering = ["-ec_id"]
    
    def __str__(self):
        return self.ec_id

