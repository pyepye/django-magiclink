from django.http.response import HttpResponse
from django.urls import include, path


def empty_view(request):
    return HttpResponse()


urlpatterns = [
    path('', empty_view, name='test_home'),
    path('auth/', include('magiclink.urls', namespace='magiclink')),
]
