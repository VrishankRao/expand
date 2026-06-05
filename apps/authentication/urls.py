from django.urls import path
from . import views

app_name = "authentication"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("verify/", views.verify_view, name="verify"),
    path("signup/", views.signup_view, name="signup"),
    path("signup/verify/", views.signup_verify_view, name="signup_verify"),
    path("logout/", views.logout_view, name="logout"),
]
