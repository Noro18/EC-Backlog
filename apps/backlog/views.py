from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView, View
from django_tables2 import RequestConfig, SingleTableView

from apps.accounts.models import User
from apps.documents.services import create_first_version  # documented exception, ARCHITECTURE.md §5
from apps.workflow.notifications import (
    queue_cd_assigned,  # documented exception, ARCHITECTURE.md §5
)

from .forms import ECCreateForm
from .models import EC, Release
from .selectors import (
    build_ec_timeline,
    cd_dashboard,
    dashboard_stats,
    des_team_dashboard,
    release_with_ec_count,
    requester_dashboard,
    search_ecs,
    visible_ecs,
)
from .services import create_ec
from .tables import EC_BADGE_CLASSES, RELEASE_BADGE_CLASSES, ECDesTeamTable, ECTable, ReleaseTable


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "backlog/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = dashboard_stats(self.request.user)
        # Only the requester pays for this extra query; the other roles never
        # read `req`, so we skip it entirely rather than render an empty dict.
        if self.request.user.role == "requester":
            context["req"] = requester_dashboard(self.request.user) #requester_dashboard ne mai husi file selector.py
        elif self.request.user.role == "cd":
            context["cd"] = cd_dashboard(self.request.user)
        elif self.request.user.role == "des_team":
            des_data = des_team_dashboard(self.request.user)
            context["des"] = des_data
            context["des_table"] = ECDesTeamTable(des_data["sent_ecs"], request=self.request)
        return context
    

class ECListView(LoginRequiredMixin, SingleTableView):
    model = EC
    table_class = ECTable  # ida ne mak nia qeury
    template_name = "backlog/ec_list.html"

    def get_queryset(self):
        params = self.request.GET
        return search_ecs(
            visible_ecs(self.request.user), # function visible_ecs ida ne'e bolu husi file selector.py
            q=params.get("q"),
            status=params.get("status"),
        )

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
                release = form.cleaned_data["release"]
                if form.wants_new_release:
                    release = create_release()  # RF02 on-demand; rolls back with the EC
                ec = create_ec(
                    requester=self.request.user,
                    reference=form.cleaned_data["reference"],
                    description=form.cleaned_data["description"],
                    release=release,
                    responsible_cd=form.cleaned_data["responsible_cd"],
                )
                if file := self.request.FILES.get("document"):
                    failed_on = "document"
                    create_first_version(ec=ec, uploaded_by=self.request.user, file=file)
                queue_cd_assigned(ec)  # RF08 — inside atomic: a rollback discards the hook
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


class RecordGoLiveView(LoginRequiredMixin, UserPassesTestMixin, View):
    """RF04: record the go-live date on a closed Release. POST-only."""

    def dispatch(self, request, *args, **kwargs):
        self.release = get_object_or_404(Release, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.role == User.Role.REQUESTER and not self.release.is_open

    def post(self, request, *args, **kwargs):
        try:
            go_live_date = date.fromisoformat(request.POST.get("go_live_date", "").strip())
        except ValueError:
            go_live_date = None
        try:
            record_go_live(self.release, request.user, go_live_date)
        except (ValidationError, PermissionDenied) as error:
            messages.error(request, getattr(error, "messages", str(error)))
        else:
            messages.success(request, f"Go-live de {self.release.release_code} registado.")
        return redirect("backlog:release_detail", pk=self.release.pk)


