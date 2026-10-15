from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from apps.backlog.models import EC

from .forms import ResubmitForm, ReviewForm, RouteToDESForm
from .models import Review
from .selectors import latest_version
from .services import approve_ec, reject_ec, resubmit_ec, route_to_des


class ReviewECView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """RF09: the assigned CD approves or rejects an in_validation EC."""

    form_class = ReviewForm
    template_name = "workflow/review_ec.html"

    def dispatch(self, request, *args, **kwargs):
        self.ec = get_object_or_404(EC, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):  # check the auth
        return (
            self.request.user.pk == self.ec.responsible_cd_id
            and self.ec.status == EC.Status.IN_VALIDATION
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ec"] = self.ec
        version = latest_version(self.ec)
        context["latest_version_number"] = version.version_number if version else None
        return context

    def form_valid(self, form):
        decision = form.cleaned_data["decision"]
        comment = form.cleaned_data["comment"]
        try:
            if decision == "approve":
                approve_ec(self.ec, self.request.user)
                messages.success(self.request, f"EC {self.ec.ec_code} aprovada.")
            else:
                reject_ec(self.ec, self.request.user, comment)
                messages.success(self.request, f"EC {self.ec.ec_code} rejeitada.")
        except (ValidationError, PermissionDenied) as error:
            # Race: status changed between GET and POST (double tab).
            # Surfaces as a form error, never a 500.
            form.add_error(None, error.messages if hasattr(error, "messages") else str(error))
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("backlog:ec_detail", args=[self.ec.pk])


class ResubmitECView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """RF05: the requester uploads a fix for a rejected EC."""

    form_class = ResubmitForm
    template_name = "workflow/resubmit_ec.html"

    def dispatch(self, request, *args, **kwargs):
        self.ec = get_object_or_404(EC, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return self.request.user.pk == self.ec.requester_id and self.ec.status == EC.Status.REJECTED

    def get_initial(self):
        return {"responsible_cd": self.ec.responsible_cd_id}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ec"] = self.ec
        context["rejection_comment"] = None
        version = latest_version(self.ec)
        if version is not None:
            try:
                context["rejection_comment"] = version.review.comment
            except Review.DoesNotExist:
                pass
        return context

    def form_valid(self, form):
        try:
            resubmit_ec(
                self.ec,
                self.request.user,
                file=self.request.FILES["document"],
                change_reason=form.cleaned_data["change_reason"],
                major=form.cleaned_data["major_change"],
                responsible_cd=form.cleaned_data["responsible_cd"],
            )
        except (ValidationError, PermissionDenied) as error:
            form.add_error(None, getattr(error, "messages", str(error)))
            return self.form_invalid(form)
        messages.success(self.request, f"EC {self.ec.ec_code} reenviada para validação.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("backlog:ec_detail", args=[self.ec.pk])


class RouteToDESView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """RF11: the approving CD forwards an approved EC to the DES team."""

    form_class = RouteToDESForm
    template_name = "workflow/route_to_des.html"

    def dispatch(self, request, *args, **kwargs):
        self.ec = get_object_or_404(EC, pk=self.kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return (
            self.request.user.pk == self.ec.responsible_cd_id
            and self.ec.status == EC.Status.APPROVED
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ec"] = self.ec
        version = latest_version(self.ec)
        context["latest_version_number"] = version.version_number if version else None
        return context

    def form_valid(self, form):
        try:
            route_to_des(self.ec, self.request.user)
        except (ValidationError, PermissionDenied) as error:
            form.add_error(None, getattr(error, "messages", str(error)))
            return self.form_invalid(form)
        messages.success(self.request, f"EC {self.ec.ec_code} enviada para a equipa DES.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("backlog:ec_detail", args=[self.ec.pk])
