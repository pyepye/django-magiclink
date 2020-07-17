from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.urls import include, path


@login_required
def needs_login(request):
    return HttpResponse()


def no_login(request):
    return HttpResponse()


urlpatterns = [
    path('no-login/', no_login, name='no_login'),
    path('needs-login/', needs_login, name='needs_login'),
    path('auth/', include('magiclink.urls', namespace='magiclink')),
]
