
from django.urls import include, path

from .views import RequiresLoginView, empty_view

urlpatterns = [
    path('empty', empty_view, name='empty'),
    path('needs-login/', RequiresLoginView.as_view(), name='needs_login'),
    path('auth/', include('magiclink.urls', namespace='magiclink')),
]
