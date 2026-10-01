from django.db import models

from apps.core.models import TimeStampedModel
from apps.documents.validators import validate_document_extension, validate_file_size


class DocumentVersion(TimeStampedModel):
    """A version of a document attached to an EC. Spec 4.5."""

    id = models.BigAutoField(primary_key=True)
    ec = models.ForeignKey(
        "backlog.EC",
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version_number = models.CharField(max_length=10)
    file = models.FileField(
        upload_to="documents/",
        max_length=255,
        validators=[validate_document_extension, validate_file_size],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="uploaded_versions",
    )
    change_reason = models.TextField(blank=True)

    def __str__(self):
        return f"{self.ec.ec_code} - {self.version_number}"

    class Meta:
        db_table = "documents_documentversion"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ec", "version_number"], name="docversion_ec_version_uniq"
            )
        ]
