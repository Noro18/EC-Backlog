from django.urls import path

from .views import (
    DocumentDownloadView,
    DocumentPreviewView,
    DocumentVersionsListView,
)

app_name = "documents"

urlpatterns = [
    path("versions/<int:pk>/preview/", DocumentPreviewView.as_view(), name="preview"),
    path("versions/<int:pk>/download/", DocumentDownloadView.as_view(), name="download"),
    path(
        "document-versions/",
        DocumentVersionsListView.as_view(),
        name="document_versions",
    ),
]
