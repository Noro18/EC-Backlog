from django.urls import path

from . import views

app_name = "backlog"

urlpatterns = [
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("ec/", views.ECListView.as_view(), name="ec_list"),
    path("release/", views.ReleaseListView.as_view(), name="release_list"),
    path("new_ec/", views.NewECView.as_view(), name="ec_form"),
    path("detail_ec/<int:pk>/", views.ECDetailView.as_view(), name="ec_detail"),
    path("detail_ec/<int:pk>/editar/", views.ECUpdateView.as_view(), name="ec_edit"),
    path("detail_release/<int:pk>/", views.ReleaseDetailView.as_view(), name="release_detail"),
    path("go_live/<int:pk>/", views.RecordGoLiveView.as_view(), name="go_live"),
    path("audit-log/", views.AuditLogListView.as_view(), name="audit_log"),
    path("pending-ecs/", views.PendingECListView.as_view(), name="pending_ecs"),
]
