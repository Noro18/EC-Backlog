from io import BytesIO
from pathlib import Path

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import TemplateView

from apps.accounts.models import User

from .models import DocumentVersion
from .selectors import ec_versions, version_ecs
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


class DocumentVersionsListView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """RF05 consultation: one chip per EC that owns document versions.

    Administrator-only read-only page (spec DOCUMENT_VERSIONS_PAGE.md):
    uploads and version numbering stay in the RF03/RF05 flows.
    """

    template_name = "documents/document_versions.html"

    def test_func(self):
        return self.request.user.role == User.Role.ADMINISTRATOR

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        context["q"] = q
        context["chips"] = version_ecs(q=q)
        return context


class ECVersionsGalleryView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """RF05 consultation: one gallery card per version of a single EC.

    404 when the EC is unknown or owns no document versions — chips only
    ever link to ECs with documents, but a typed URL must fail safely.
    """

    template_name = "documents/ec_versions_gallery.html"

    def test_func(self):
        return self.request.user.role == User.Role.ADMINISTRATOR

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        versions = list(ec_versions(self.kwargs["ec_pk"]))
        if not versions:
            raise Http404("This EC has no document versions.")
        context["ec"] = versions[0].ec
        context["versions"] = versions
        return context
