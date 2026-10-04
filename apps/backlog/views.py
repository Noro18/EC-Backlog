from django.views.generic import TemplateView, DetailView
from django_tables2 import SingleTableView

from .models import EC, Release
from .selectors import release_with_ec_count
from .tables import ECTable, ReleaseTable


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
    context_object_name = "release"

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            "ecs__requester", "ecs__responsible_cd"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        release = self.object

        context["ec_table"] = ECTable(
            release.ecs.select_related("requester", "responsible_cd", "release"),
            exclude=("release", "description", "action" , "is_imported"),
        )

        used = release.ec_count
        capacity = release.capacity or 1
        context["ec_used"] = used
        context["percent"] = min(round(used / capacity * 100), 100)
        return context
