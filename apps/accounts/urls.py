from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import TTLoginView, UserCreateView, UserDeactivateView, UserListView, UserUpdateView

app_name = "accounts"

urlpatterns = [
    path("", TTLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/novo/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/editar/", UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/apagar/", UserDeactivateView.as_view(), name="user_deactivate"),
]
