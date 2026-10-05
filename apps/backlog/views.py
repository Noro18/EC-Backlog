from django.views.generic import DetailView, TemplateView
from django_tables2 import RequestConfig, SingleTableView

from .models import EC, Release
from .selectors import release_with_ec_count
from .tables import RELEASE_BADGE_CLASSES, ECTable, ReleaseTable


class ECListView(SingleTableView):
    model = EC
    table_class = ECTable  # ida ne mak nia qeury
    template_name = "backlog/ec_list.html"


class ReleaseListView(SingleTableView):
    model = Release
    table_class = ReleaseTable
    template_name = "backlog/release_list.html"

    def get_queryset(self):  # this is reserved function
        return release_with_ec_count()


class NewECView(TemplateView):
    template_name = "backlog/ec_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.accounts.models import User

        from .models import Release

        context["releases"] = Release.objects.all()
        context["reviewers"] = User.objects.filter(role="cd")
        return context


class ECDetailView(TemplateView):
    template_name = "backlog/ec_detail.html"


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
