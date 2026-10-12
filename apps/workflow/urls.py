from django.urls import path

from .views import ResubmitECView, ReviewECView

app_name = "workflow"

urlpatterns = [
    path("review_ec/<int:pk>/", ReviewECView.as_view(), name="review_ec"),
    path("resubmit_ec/<int:pk>/", ResubmitECView.as_view(), name="resubmit_ec"),
]
