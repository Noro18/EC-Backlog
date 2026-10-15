from django.urls import path

from .views import ResubmitECView, ReviewECView, RouteToDESView

app_name = "workflow"

urlpatterns = [
    path("review_ec/<int:pk>/", ReviewECView.as_view(), name="review_ec"),
    path("resubmit_ec/<int:pk>/", ResubmitECView.as_view(), name="resubmit_ec"),
    path("route_to_des/<int:pk>/", RouteToDESView.as_view(), name="route_to_des"),
]
