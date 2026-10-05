from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import TTLoginView, UserListView

app_name = "accounts"

urlpatterns = [
    path("", TTLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("users/", UserListView.as_view(), name="user_list"),
]
