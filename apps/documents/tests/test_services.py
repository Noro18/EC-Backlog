import subprocess
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.backlog.tests.factories import ECFactory, UserFactory
from apps.documents.services import (
    DocumentConversionError,
    convert_docx_to_pdf,
    create_first_version,
    create_next_version,
)

pytestmark = pytest.mark.django_db


class TestCreateNextVersion:
    def test_minor_bump(self):
        ec = ECFactory()
        user = UserFactory()
        first = create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )
        assert first.version_number == "v1.0"

        second = create_next_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"fixed content"),
            uploaded_by=user,
            change_reason="added the missing diagram",
        )

        assert second.version_number == "v1.1"
        assert ec.versions.count() == 2

    def test_major_bump(self):
        ec = ECFactory()
        user = UserFactory()
        create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )
        second = create_next_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"fixed content"),
            uploaded_by=user,
            change_reason="added the missing diagram",
            major=True,
        )

        assert second.version_number == "v2.0"
        assert ec.versions.count() == 2

    def test_blank_reason_refused(self):
        ec = ECFactory()
        user = UserFactory()
        create_first_version(
            ec=ec,
            file=SimpleUploadedFile("spec.pdf", b"first content"),
            uploaded_by=user,
            change_reason="initial",
        )

        with pytest.raises(ValidationError):
            create_next_version(
                ec=ec,
                file=SimpleUploadedFile("spec.pdf", b"fixed content"),
                uploaded_by=user,
                change_reason="   ",
            )

        assert ec.versions.count() == 1


class TestConvertDocxToPdf:
    def test_converts_docx_to_pdf_and_returns_the_pdf_bytes(self, monkeypatch):
        docx = SimpleUploadedFile("spec.docx", b"original DOCX bytes")
        monkeypatch.setenv("LIBREOFFICE_BINARY", "/mock/soffice")

        def fake_run(command, **kwargs):
            input_path = Path(command[-1])
            input_path.with_suffix(".pdf").write_bytes(b"%PDF-converted")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        pdf = convert_docx_to_pdf(docx)

        assert pdf == b"%PDF-converted"

    def test_missing_libreoffice_raises_a_clear_conversion_error(self, monkeypatch):
        docx = SimpleUploadedFile("spec.docx", b"original DOCX bytes")
        monkeypatch.delenv("LIBREOFFICE_BINARY", raising=False)
        monkeypatch.setattr("apps.documents.services.shutil.which", lambda _name: None)

        with pytest.raises(DocumentConversionError, match="LibreOffice"):
            convert_docx_to_pdf(docx)

    def test_conversion_timeout_raises_a_conversion_error(self, monkeypatch):
        docx = SimpleUploadedFile("spec.docx", b"original DOCX bytes")
        monkeypatch.setenv("LIBREOFFICE_BINARY", "/mock/soffice")

        def timeout(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("soffice", timeout=30)

        monkeypatch.setattr(subprocess, "run", timeout)

        with pytest.raises(DocumentConversionError, match="timed out"):
            convert_docx_to_pdf(docx)
