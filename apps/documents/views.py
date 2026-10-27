from io import BytesIO
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import DocumentVersion
from .services import DocumentConversionError, convert_docx_to_pdf


def _get_document_file(pk):
    version = get_object_or_404(DocumentVersion, pk=pk)
    if not version.file:
        raise Http404("No file is attached to this document version.")
    return version


@method_decorator(xframe_options_sameorigin, name="dispatch")
class DocumentPreviewView(LoginRequiredMixin, View):
    """Serve a PDF preview, converting DOCX temporarily when needed."""

    def get(self, request, pk):
        version = _get_document_file(pk)
        filename = Path(version.file.name).name
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            return FileResponse(
                version.file.open("rb"),
                as_attachment=False,
                filename=filename,
                content_type="application/pdf",
            )

        if suffix == ".docx":
            try:
                pdf_bytes = convert_docx_to_pdf(version.file)
            except DocumentConversionError:
                return HttpResponse(
                    "A pré-visualização não está disponível. Descarregue o documento original.",
                    status=422,
                    content_type="text/plain; charset=utf-8",
                )

            return FileResponse(
                BytesIO(pdf_bytes),
                as_attachment=False,
                filename=f"{Path(filename).stem}.pdf",
                content_type="application/pdf",
            )

        return HttpResponse(
            "Este formato não tem pré-visualização. Descarregue o documento original.",
            status=415,
            content_type="text/plain; charset=utf-8",
        )


class DocumentDownloadView(LoginRequiredMixin, View):
    """Download the original uploaded file without converting or replacing it."""

    def get(self, request, pk):
        version = _get_document_file(pk)
        return FileResponse(
            version.file.open("rb"),
            as_attachment=True,
            filename=Path(version.file.name).name,
        )
