from django.urls import path

from .views import Login, LoginSent, LoginVerify, Logout, Signup

app_name = "magiclink"

urlpatterns = [
    path('login/', Login.as_view(), name='login'),
    path('login/sent/', LoginSent.as_view(), name='login_sent'),
    path('signup/', Signup.as_view(), name='signup'),
    path('login/verify/', LoginVerify.as_view(), name='login_verify'),
    path('logout/', Logout.as_view(), name='logout'),
]
