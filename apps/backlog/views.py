
from django.views.generic import TemplateView

class EClistView(TemplateView):
    template_name = "backlog/ec_list.html"


class ReleaseListView(TemplateView):
    template_name = "backlog/release_list.html"

class NewECView(TemplateView):
    template_name = "backlog/ec_form.html"

class ECDetailView(TemplateView):
    template_name = "backlog/ec_detail.html"