import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError

from .models import DocumentVersion


class DocumentConversionError(RuntimeError):
    """Raised when a DOCX file cannot be converted to a preview PDF."""


def _libreoffice_binary():
    """Find LibreOffice on PATH, or use an explicit configured executable path."""
    configured_path = os.environ.get("LIBREOFFICE_BINARY")
    if configured_path:
        return configured_path

    return (
        shutil.which("soffice")
        or shutil.which("soffice.exe")
        or shutil.which("soffice.com")
    )


def convert_docx_to_pdf(source_file) -> bytes:
    """Convert a DOCX file to temporary PDF bytes without altering the original.

    LibreOffice must be installed on the server. The PDF is generated in a temporary
    directory and returned in memory; it is not stored as another DocumentVersion.
    """
    if Path(source_file.name).suffix.lower() != ".docx":
        raise DocumentConversionError("Only DOCX files can be converted for preview.")

    executable = _libreoffice_binary()
    if not executable:
        raise DocumentConversionError(
            "LibreOffice was not found. Install it or configure LIBREOFFICE_BINARY."
        )

    try:
        with TemporaryDirectory(prefix="ec-doc-preview-") as temporary_directory:
            work_dir = Path(temporary_directory)
            source_path = work_dir / "source.docx"
            pdf_path = work_dir / "source.pdf"
            profile_path = work_dir / "libreoffice-profile"
            profile_path.mkdir()

            with source_file.open("rb") as uploaded_file:
                source_path.write_bytes(uploaded_file.read())

            subprocess.run(
                [
                    executable,
                    "--headless",
                    f"-env:UserInstallation={profile_path.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(work_dir),
                    str(source_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
                raise DocumentConversionError(
                    "LibreOffice did not produce a readable PDF preview."
                )
            return pdf_path.read_bytes()
    except subprocess.TimeoutExpired as error:
        raise DocumentConversionError("DOCX to PDF conversion timed out.") from error
    except (OSError, subprocess.CalledProcessError) as error:
        raise DocumentConversionError("DOCX to PDF conversion failed.") from error


def create_first_version(ec, file, uploaded_by, change_reason=""):
    """RF06: store the first document version for an EC — always v1.0 (RF06)."""
    version = DocumentVersion(
        ec=ec,
        version_number="v1.0",
        file=file,
        uploaded_by=uploaded_by,
        change_reason=change_reason,
    )
    version.full_clean()  # Validate before saving
    version.save()
    return version


def create_next_version(ec, file, uploaded_by, change_reason="", major=False):
    """RF05: store a follow-up version — minor bump (v1.0 → v1.1) by default,
    major bump (v1.2 → v2.0) when major=True."""

    if not (change_reason or "").strip():
        raise ValidationError("Change reason must not be empty for a re-upload.")

    latest = ec.versions.order_by("-uploaded_at").first()

    if latest is None:
        raise ValidationError("This EC has no versions yet — upload v1.0 first.")
    pieces = latest.version_number[1:].split(".")
    if len(pieces) != 2:
        raise ValidationError(f"Unknown version format: {latest.version_number}.")
    try:
        current_major = int(pieces[0])
        current_minor = int(pieces[1])
    except ValueError:
        raise ValidationError(f"Unknown version format: {latest.version_number}.")
    if major:
        next_number = f"v{current_major + 1}.0"
    else:
        next_number = f"v{current_major}.{current_minor + 1}"

    version = DocumentVersion(
        ec=ec,
        version_number=next_number,
        file=file,
        uploaded_by=uploaded_by,
        change_reason=change_reason,
    )
    version.full_clean()
    version.save()
    return version
