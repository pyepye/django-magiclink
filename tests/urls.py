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

    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)

        from magiclink import settings
        from magiclink.models import MagicLink

        url = reverse('no_login')
        response = HttpResponseRedirect(url)

        if settings.REQUIRE_SAME_BROWSER:
            token = self.request.GET.get('token')
            magiclink = MagicLink.objects.get(token=token)
            cookie_name = f'magiclink{magiclink.pk}'
            response.delete_cookie(cookie_name, magiclink.cookie_value)

        return response


urlpatterns = [
    path('no-login/', no_login, name='no_login'),
    path('needs-login/', needs_login, name='needs_login'),
    path('custom-login-verify/', CustomLoginVerify.as_view(), name='custom_login_verify'),  # NOQA: E501
    path('auth/', include('magiclink.urls', namespace='magiclink')),
]
