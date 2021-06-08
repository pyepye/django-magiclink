from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse, HttpResponseRedirect
from django.urls import include, path, reverse

from magiclink.views import LoginVerify


@login_required
def needs_login(request):
    return HttpResponse()


def no_login(request):
    return HttpResponse()


class CustomLoginVerify(LoginVerify):

    def login_complete_action(self) -> HttpResponse:
        url = reverse('no_login')
        return HttpResponseRedirect(url)


urlpatterns = [
    path('no-login/', no_login, name='no_login'),
    path('needs-login/', needs_login, name='needs_login'),
    path('custom-login-verify/', CustomLoginVerify.as_view(), name='custom_login_verify'),  # NOQA: E501
    path('auth/', include('magiclink.urls', namespace='magiclink')),
]
