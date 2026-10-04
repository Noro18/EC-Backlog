from django.contrib.auth.views import LoginView


class TTLoginView(LoginView):
    template_name = "accounts/login.html"
    
