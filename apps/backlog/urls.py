from django.urls import path

from . import views

app_name = "backlog"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("ec/", views.ECListView.as_view(), name="ec_list"),
    path("release/", views.ReleaseListView.as_view(), name="release_list"),
    path("new_ec/", views.NewECView.as_view(), name="ec_form"),
    path("detail_ec/<int:pk>/", views.ECDetailView.as_view(), name="ec_detail"),
    path("detail_release/<int:pk>/", views.ReleaseDetailView.as_view(), name="release_detail"),
    path("go_live/<int:pk>/", views.RecordGoLiveView.as_view(), name="go_live"),
]
