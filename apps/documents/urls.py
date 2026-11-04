from django.urls import path

from .views import DocumentDownloadView, DocumentPreviewView

app_name = "documents"

urlpatterns = [
    path("versions/<int:pk>/preview/", DocumentPreviewView.as_view(), name="preview"),
    path("versions/<int:pk>/download/", DocumentDownloadView.as_view(), name="download"),
]
