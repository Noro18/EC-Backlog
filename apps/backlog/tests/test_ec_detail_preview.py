import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.backlog.tests.factories import ECFactory
from apps.documents.tests.factories import DocumentVersionFactory

pytestmark = pytest.mark.django_db


def add_version(ec, number, filename):
    return DocumentVersionFactory(
        ec=ec,
        uploaded_by=ec.requester,
        version_number=number,
        file=SimpleUploadedFile(filename, b"test document bytes"),
    )


class TestECDetailPreview:
    def test_only_the_latest_pdf_is_embedded_and_older_versions_are_downloadable(
        self, client
    ):
        ec = ECFactory(release=None)
        older = add_version(ec, "v1.0", "older.pdf")
        latest = add_version(ec, "v1.1", "latest.pdf")
        client.force_login(ec.requester)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        html = response.content.decode()

        assert response.status_code == 200
        assert reverse("documents:preview", args=[latest.pk]) in html
        assert reverse("documents:preview", args=[older.pk]) not in html
        assert reverse("documents:download", args=[older.pk]) in html
        assert reverse("documents:download", args=[latest.pk]) in html

    def test_latest_docx_is_previewable(self, client):
        ec = ECFactory(release=None)
        latest = add_version(ec, "v1.0", "latest.docx")
        client.force_login(ec.requester)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        html = response.content.decode()

        assert response.status_code == 200
        assert reverse("documents:preview", args=[latest.pk]) in html
        assert reverse("documents:download", args=[latest.pk]) in html

    def test_unsupported_file_has_download_but_no_preview(self, client):
        ec = ECFactory(release=None)
        document = add_version(ec, "v1.0", "spec.txt")
        client.force_login(ec.requester)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        html = response.content.decode()

        assert response.status_code == 200
        assert "<iframe" not in html
        assert "Este tipo de ficheiro não tem pré-visualização." in html
        assert reverse("documents:download", args=[document.pk]) in html

    def test_ec_without_versions_has_no_preview_frame(self, client):
        ec = ECFactory(release=None)
        client.force_login(ec.requester)

        response = client.get(reverse("backlog:ec_detail", args=[ec.pk]))
        html = response.content.decode()

        assert response.status_code == 200
        assert "<iframe" not in html
        assert "Ainda sem documentos." in html
