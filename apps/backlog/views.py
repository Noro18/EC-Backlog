from django.views.generic import TemplateView
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


class ECDetailView(TemplateView):
    template_name = "backlog/ec_detail.html"
