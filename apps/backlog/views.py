
from django.views.generic import TemplateView
from django_tables2 import SingleTableView

from .models import EC
from .tables import ECTable


class EClistView(SingleTableView):
    model = EC
    table_class = ECTable # ida ne mak nia qeury 
    template_name = "backlog/ec_list.html"
    


class ReleaseListView(TemplateView):
    template_name = "backlog/release_list.html"

class NewECView(TemplateView):
    template_name = "backlog/ec_form.html"

class ECDetailView(TemplateView):
    template_name = "backlog/ec_detail.html"