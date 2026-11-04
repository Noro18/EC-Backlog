from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, TemplateView, UpdateView, View
from django_tables2 import RequestConfig, SingleTableView

from apps.accounts.models import User
from apps.documents.services import create_first_version  # documented exception, ARCHITECTURE.md §5
from apps.workflow.notifications import (
    queue_cd_assigned,  # documented exception, ARCHITECTURE.md §5
)

from .forms import ECCreateForm, ECEditForm
from .models import EC, Release
from .selectors import (
    admin_dashboard,
    build_ec_timeline,
    cd_dashboard,
    dashboard_stats,
    des_team_dashboard,
    full_audit_log_entries,
    pending_ecs,
    release_with_ec_count,
    requester_dashboard,
    search_ecs,
    visible_ecs,
)
from .services import can_edit_ec, create_ec, create_release, record_go_live, update_ec
from .tables import (
    EC_BADGE_CLASSES,
    RELEASE_BADGE_CLASSES,
    ActivityTable,
    CDPendingReviewTable,
    ECDesTeamTable,
    ECRequesterTable,
    ECTable,
    FullAuditLogTable,
    PendingECTable,
    ReleaseTable,
)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "backlog/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = dashboard_stats(self.request.user)
        # Only the requester pays for this extra query; the other roles never
        # read `req`, so we skip it entirely rather than render an empty dict.
        if self.request.user.role == "requester":
            req_data = requester_dashboard(self.request.user)
            context["req"] = req_data
            context["req_table"] = ECRequesterTable(req_data["my_ecs"], request=self.request)
        elif self.request.user.role == "cd":
            cd_data = cd_dashboard(self.request.user)
            context["cd"] = cd_data
            context["cd_table"] = CDPendingReviewTable(cd_data["pending_review"], request=self.request)
        elif self.request.user.role == "des_team":
            des_data = des_team_dashboard(self.request.user)
            context["des"] = des_data
            context["des_table"] = ECDesTeamTable(des_data["sent_ecs"], request=self.request)
        elif self.request.user.role == "administrator":
            # Admin-only: the metrics are never built for other roles, so no
            # admin data leaks outside the admin panel. The user list itself
            # lives on the `Gestão de Utilizadores` page (accounts:user_list).
            context["admin"] = admin_dashboard(self.request.user)
            context["log_table"] = ActivityTable(
                context["admin"]["recent_logs"], request=self.request
            )
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
        context["can_edit"] = can_edit_ec(ec, self.request.user)
        versions = list(ec.versions.all())
        latest_version = versions[0] if versions else None
        context["latest_document_version"] = latest_version
        context["latest_document_can_preview"] = bool(
            latest_version
            and latest_version.file
            and latest_version.file.name.lower().endswith((".pdf", ".docx"))
        )
        return context


class ECUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Issue #67 / EC_EDIT.md: correct the content of an EC that is in flight.

    The save goes through `update_ec`, never through `form.save()` — the
    service re-checks the status, the ownership and the Release capacity.
    """

    model = EC
    form_class = ECEditForm
    template_name = "backlog/ec_edit.html"
    context_object_name = "ec"

    def test_func(self):
        return can_edit_ec(self.get_object(), self.request.user)

    def form_valid(self, form):
        try:
            update_ec(
                self.object,
                self.request.user,
                reference=form.cleaned_data["reference"],
                description=form.cleaned_data["description"],
                release=form.cleaned_data["release"],
                responsible_cd=form.cleaned_data["responsible_cd"],
            )
        except (ValidationError, PermissionDenied) as error:
            # A stale tab (status or capacity moved on) is a form error, not a 500.
            form.add_error(None, getattr(error, "messages", str(error)))
            return self.form_invalid(form)
        messages.success(self.request, f"EC {self.object.ec_code} atualizada.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("backlog:ec_detail", kwargs={"pk": self.object.pk})


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

class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, SingleTableView):
    """Administrator-only full audit log view."""

    table_class = FullAuditLogTable
    template_name = "backlog/audit_log.html"
    paginate_by = 25

    def test_func(self):
        return self.request.user.role == User.Role.ADMINISTRATOR

    def get_queryset(self):
        return full_audit_log_entries()


class PendingECListView(LoginRequiredMixin, UserPassesTestMixin, SingleTableView):
    table_class = PendingECTable
    template_name = "backlog/pending_ecs.html"
    paginate_by = 25

    def test_func(self):
        return self.request.user.role in (
            User.Role.CD,
            User.Role.ADMINISTRATOR,
        )

    def get_queryset(self):
        return pending_ecs(self.request.user)

