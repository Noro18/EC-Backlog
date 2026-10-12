from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView
from django_tables2 import RequestConfig, SingleTableView

from apps.accounts.models import User
from apps.documents.services import create_first_version  # documented exception, ARCHITECTURE.md §5

from .forms import ECCreateForm
from .models import EC, Release
from .selectors import (
    build_ec_timeline,
    dashboard_stats,
    release_with_ec_count,
    requester_dashboard,
    cd_dashboard,
    visible_ecs,
)
from .services import create_ec
from .tables import EC_BADGE_CLASSES, RELEASE_BADGE_CLASSES, ECTable, ReleaseTable


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "backlog/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = dashboard_stats(self.request.user)
        # Only the requester pays for this extra query; the other roles never
        # read `req`, so we skip it entirely rather than render an empty dict.
        if self.request.user.role == "requester":
            context["req"] = requester_dashboard(self.request.user)
        elif self.request.user.role == "cd":
            context["cd"] = cd_dashboard(self.request.user)
        return context
    

class ECListView(LoginRequiredMixin, SingleTableView):
    model = EC
    table_class = ECTable  # ida ne mak nia qeury
    template_name = "backlog/ec_list.html"

    def get_queryset(self):
        return visible_ecs(self.request.user)

class ReleaseListView(SingleTableView):
    model = Release
    table_class = ReleaseTable
    template_name = "backlog/release_list.html"

    def get_queryset(self):  # this is reserved function
        return release_with_ec_count()


class NewECView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    form_class = ECCreateForm
    template_name = "backlog/ec_form.html"
    success_url = reverse_lazy("backlog:ec_list")

    def test_func(self):
        return self.request.user.role in [User.Role.REQUESTER, User.Role.ADMINISTRATOR]

    def form_valid(self, form):
        failed_on = "release"
        try:
            with transaction.atomic():
                ec = create_ec(
                    requester=self.request.user,
                    reference=form.cleaned_data["reference"],
                    description=form.cleaned_data["description"],
                    release=form.cleaned_data["release"],
                    responsible_cd=form.cleaned_data["responsible_cd"],
                )
                if file := self.request.FILES.get("document"):
                    failed_on = "document"
                    create_first_version(ec=ec, uploaded_by=self.request.user, file=file)
        except ValidationError as error:
            # full_clean() raises a message_dict ({"file": [...]}) — flatten it so
            # the message can attach to OUR field name (document vs release).
            form.add_error(failed_on, error.messages)
            return self.form_invalid(form)
        messages.success(self.request, f"EC {ec.ec_code} criada com sucesso.")
        # NOT super().form_valid(form): that would call form.save() and mint a
        # second, serviceless EC row (the spec sketch's shortcut is a double-save).
        return HttpResponseRedirect(self.success_url)


class ECDetailView(LoginRequiredMixin, DetailView):
    model = EC
    template_name = "backlog/ec_detail.html"
    context_object_name = "ec"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("requester", "responsible_cd", "release")
            .prefetch_related("versions__uploaded_by", "versions__review")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ec = self.object
        context["status_badge_class"] = EC_BADGE_CLASSES.get(ec.status, "text-bg-secondary")
        context["timeline"] = build_ec_timeline(ec)
        return context


class ReleaseDetailView(DetailView):
    model = Release
    template_name = "backlog/release_detail.html"
    # iha template it aatu access oinsa uza context_object_name
    context_object_name = "release"

    # this is reserved function: it modfy the the stargin point of the tbale.
    # or prepar wheat we will be owrking with.
    def get_queryset(self):
        return release_with_ec_count()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        release = self.object

        context["ec_table"] = ECTable(
            release.ecs.select_related("requester", "responsible_cd"),
            exclude=("release", "description", "action", "is_imported"),
        )

        context["ec_used"] = release.ec_total
        context["status_badge_class"] = RELEASE_BADGE_CLASSES[release.status_label]
        RequestConfig(self.request).configure(context["ec_table"])
        return context
