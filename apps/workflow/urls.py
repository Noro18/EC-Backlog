from django.urls import path

from .views import ReviewECView

app_name = "workflow"

urlpatterns = [
    path("review_ec/<int:pk>/", ReviewECView.as_view(), name="review_ec"),
]
