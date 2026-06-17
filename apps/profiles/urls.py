from django.urls import path
from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("setup/", views.create_profile_view, name="create_profile"),
    path("update/", views.update_profile_view, name="update_profile"),
    path("email/send-otp/", views.send_email_otp_view, name="send_email_otp"),
    path("email/verify-otp/", views.verify_email_otp_view, name="verify_email_otp"),
    path("links/add/", views.add_link_view, name="add_link"),
    path("links/toggle/<int:pk>/", views.toggle_link_view, name="toggle_link"),
    path("links/delete/<int:pk>/", views.delete_link_view, name="delete_link"),
    path("links/sort/", views.sort_links_view, name="sort_links"),
    path("links/list/", views.links_list_view, name="links_list"),
    path("links/edit/<int:pk>/", views.edit_link_view, name="edit_link"),
    path("links/analytics/<int:pk>/", views.link_analytics_view, name="link_analytics"),
    path("links/insights/", views.link_insights_view, name="link_insights"),
    path("theme/update/", views.update_theme_view, name="update_theme"),
    path("search-handle/", views.search_handle_view, name="search_handle"),
]

