from django.urls import path

from . import views

app_name = "backlog"

urlpatterns = [
    path("ec/", views.ECListView.as_view(), name="ec_list"),
    path("release/", views.ReleaseListView.as_view(), name="release_list"),
    path("new_ec/", views.NewECView.as_view(), name="ec_form"),
    path("detail_ec/<int:pk>/", views.ECDetailView.as_view(), name="ec_detail"),
]