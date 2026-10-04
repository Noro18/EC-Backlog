from django.views.generic import DetailView, TemplateView
from django_tables2 import SingleTableView

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


class ReleaseDetailView(DetailView):
    model = Release
    template_name = "backlog/release_detail.html"
    context_object_name = "release"

    def get_queryset(self):
        return release_with_ec_count()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_badge_class"] = RELEASE_BADGE_CLASSES[self.object.status_label]
        return context


class NewECView(TemplateView):
    template_name = "backlog/ec_form.html"


class ECDetailView(TemplateView):
    template_name = "backlog/ec_detail.html"
