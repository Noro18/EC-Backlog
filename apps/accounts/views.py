from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, View
from django_tables2 import SingleTableView

from .forms import UserCreateForm, UserUpdateForm
from .models import User
from .selectors import list_users
from .services import create_user, deactivate_user, update_user
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


class UserUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def test_func(self):
        return self.request.user.role == "administrator"

    def form_valid(self, form):
        self.object = update_user(form)
        messages.success(self.request, f"Utilizador {self.object.username} atualizado com sucesso.")
        return HttpResponseRedirect(self.success_url)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_edit"] = True
        return context


class UserDeactivateView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.role == "administrator"

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=self.kwargs["pk"])
        try:
            deactivate_user(user, request.user)
        except ValidationError as error:
            messages.error(request, error.messages[0] if hasattr(error, "messages") else str(error))
        else:
            messages.success(request, f"Utilizador {user.username} desativado com sucesso.")
        return redirect("accounts:user_list")
