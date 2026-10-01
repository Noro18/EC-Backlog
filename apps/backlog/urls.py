from django.urls import path

from . import views

app_name = "backlog"

urlpatterns = [
    path("ec/", views.EClistView.as_view(), name="ec_list"),
    path("lancamento/", views.ReleaseListView.as_view(), name="release_list"),
    path("newEC/", views.NewECView.as_view(), name="ec_form"),
    path("detailEC/", views.ECDetailView.as_view(), name="ec_detail"),
]