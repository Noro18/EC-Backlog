from django.db import models

from apps.core.models import TimeStampedModel


class Review(TimeStampedModel):
    """A CD decision on one DocumentVersion. Spec 4.6."""

    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.BigAutoField(primary_key=True)
    document_version = models.OneToOneField(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="review",
    )
    cd = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="cd_reviews",
    )
    comment = models.TextField(blank=True)
    decision = models.CharField(max_length=10, choices=Decision.choices)
    decided_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.cd} for {self.document_version}"

    class Meta:
        db_table = "workflow_review"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(decision="rejected") | ~models.Q(comment=""),
                name="review_rejection_requires_comment",
            )
        ]
