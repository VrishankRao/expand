from django.urls import path
from . import views

app_name = "leads"

urlpatterns = [
    # Dashboard operations
    path("dashboard/leads/search/", views.search_leads_view, name="search_leads"),
    path("dashboard/leads/export/", views.export_leads_view, name="export_leads"),
    
    # Public profile and lead capturing
    path("<str:handle>/", views.public_profile_view, name="public_profile"),
    path("<str:handle>/capture/<int:link_id>/", views.capture_lead_view, name="capture_lead"),
]
