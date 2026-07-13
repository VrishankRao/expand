from django.urls import path
from . import views

app_name = "admin_panel"

urlpatterns = [
    path("login/", views.admin_login_view, name="login"),
    path("logout/", views.admin_logout_view, name="logout"),
    path("", views.admin_dashboard_view, name="dashboard"),
    path("user/<str:handle>/", views.admin_user_detail_view, name="user_detail"),
    path("toggle-visibility/<str:handle>/", views.admin_toggle_visibility_view, name="toggle_visibility"),
    path("user/<str:handle>/delete/", views.admin_delete_user_view, name="delete_user"),
    path("links/analytics/<int:pk>/", views.admin_link_analytics_view, name="link_analytics"),
]
