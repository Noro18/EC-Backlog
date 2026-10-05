from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django_tables2 import SingleTableView

from .selectors import list_users
from .tables import UserTable


class TTLoginView(LoginView):
    template_name = "accounts/login.html"


class UserListView(LoginRequiredMixin, UserPassesTestMixin, SingleTableView):
    table_class = UserTable
    template_name = "accounts/user_list.html"

    def get_queryset(self):
        return list_users()
    
    def test_func(self):
        return self.request.user.role == "administrator"
    
    
    
    
