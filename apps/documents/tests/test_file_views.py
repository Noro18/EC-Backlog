import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import User
from apps.backlog.tests.factories import UserFactory
from apps.documents.services import DocumentConversionError
from apps.documents.tests.factories import DocumentVersionFactory

pytestmark = pytest.mark.django_db


def make_document(filename, content):
    return DocumentVersionFactory(
        file=SimpleUploadedFile(
            filename,
            content,
            content_type="application/octet-stream",
        )
    )


def response_bytes(response):
    if response.streaming:
        return b"".join(response.streaming_content)
    return response.content


class TestDocumentFileAccess:
    @pytest.mark.parametrize(
        "route_name",
        ["documents:preview", "documents:download"],
    )
    def test_anonymous_user_is_redirected_to_login(self, client, route_name):
        document = make_document("spec.pdf", b"%PDF-original")

        response = client.get(reverse(route_name, args=[document.pk]))

        assert response.status_code == 302
        assert "?next=" in response.url

    @pytest.mark.parametrize(
        "role",
        [
            User.Role.REQUESTER,
            User.Role.CD,
            User.Role.DES_TEAM,
            User.Role.ADMINISTRATOR,
        ],
    )
    def test_all_authenticated_roles_can_preview_and_download(self, client, role):
        document = make_document("spec.pdf", b"%PDF-original")
        client.force_login(UserFactory(role=role))

        response = client.get(reverse("documents:preview", args=[document.pk]))
        download = client.get(reverse("documents:download", args=[document.pk]))

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert response["Content-Disposition"].startswith("inline;")
        assert response["X-Frame-Options"] == "SAMEORIGIN"
        assert download.status_code == 200
        assert download["Content-Disposition"].startswith("attachment;")

    def test_pdf_preview_returns_original_pdf_bytes(self, client):
        pdf_content = b"%PDF-1.4\nPDF test content"
        document = make_document("spec.pdf", pdf_content)
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        response = client.get(reverse("documents:preview", args=[document.pk]))

        assert response.status_code == 200
        assert response_bytes(response) == pdf_content

    def test_docx_preview_converts_but_download_returns_original_docx(
        self, client, monkeypatch
    ):
        docx_content = b"original DOCX content"
        document = make_document("spec.docx", docx_content)

        def fake_convert_docx_to_pdf(source_file):
            assert source_file.name.endswith(".docx")
            return b"%PDF-converted preview"

        monkeypatch.setattr(
            "apps.documents.views.convert_docx_to_pdf",
            fake_convert_docx_to_pdf,
            raising=False,
        )
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        preview = client.get(reverse("documents:preview", args=[document.pk]))
        download = client.get(reverse("documents:download", args=[document.pk]))

        assert preview.status_code == 200
        assert preview["Content-Type"] == "application/pdf"
        assert response_bytes(preview) == b"%PDF-converted preview"

        assert download.status_code == 200
        assert download["Content-Disposition"].startswith("attachment;")
        assert response_bytes(download) == docx_content

    def test_docx_conversion_failure_returns_a_friendly_preview_message(
        self, client, monkeypatch
    ):
        document = make_document("spec.docx", b"original DOCX content")

        def fail_conversion(_source_file):
            raise DocumentConversionError("LibreOffice is unavailable.")

        monkeypatch.setattr(
            "apps.documents.views.convert_docx_to_pdf",
            fail_conversion,
        )
        client.force_login(UserFactory(role=User.Role.REQUESTER))

        response = client.get(reverse("documents:preview", args=[document.pk]))

        assert response.status_code == 422
        assert "A pré-visualização não está disponível" in response.content.decode()

    def test_raw_media_url_does_not_bypass_authenticated_download(self, client):
        document = make_document("spec.pdf", b"%PDF-original")

        response = client.get(document.file.url)

        assert response.status_code == 404
