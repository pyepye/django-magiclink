from django.contrib.auth.mixins import LoginRequiredMixin
from django.http.response import HttpResponse
from django.views.generic import TemplateView


class RequiresLoginView(LoginRequiredMixin, TemplateView):
    template_name = 'login.html'


def empty_view(request):
    return HttpResponse()
