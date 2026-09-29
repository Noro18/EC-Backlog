from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

MAX_FILE_SIZE_MB = 10  # Maximum file size in megabytes
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes

validate_document_extension = FileExtensionValidator(allowed_extensions=["pdf", "docx"])


def validate_file_size(file):
    """Validate that the uploaded file does not exceed the maximum size."""
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(f"File size should not exceed {MAX_FILE_SIZE_MB} MB.")
