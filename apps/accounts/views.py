from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django_tables2 import SingleTableView

from .forms import UserCreateForm
from .selectors import list_users
from .services import create_user
from .tables import UserTable


class TTLoginView(LoginView):
    template_name = "accounts/login.html"


class UserListView(LoginRequiredMixin, UserPassesTestMixin, SingleTableView):
    table_class = UserTable
    template_name = "accounts/user_list.html"

    def get_queryset(self):
        return list_users(self.request.GET.get("q"))
    
    def test_func(self):
        return self.request.user.role == "administrator"
    

class UserCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """USER_CREATE.md: same gate as UserListView, saving through the service."""

    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def test_func(self):
        return self.request.user.role == "administrator"

    def form_valid(self, form):
        # NOT super().form_valid(form) — that would call form.save() a second
        # time. The service is the single write point (Decision 5).
        self.object = create_user(form)
        return HttpResponseRedirect(self.get_success_url())
    
    
