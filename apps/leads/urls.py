from django.urls import path
from . import views

app_name = "leads"

urlpatterns = [
    # Dashboard operations
    path("dashboard/leads/search/", views.search_leads_view, name="search_leads"),
    path("dashboard/leads/export/", views.export_leads_view, name="export_leads"),
    
    # OTP Verification for lead form
    path("leads/otp/send/", views.send_lead_otp_view, name="send_otp"),
    path("leads/otp/verify/", views.verify_lead_otp_view, name="verify_otp"),

    # Public profile and lead capturing
    path("<str:handle>/", views.public_profile_view, name="public_profile"),
    path("<str:handle>/capture/<int:link_id>/", views.capture_lead_view, name="capture_lead"),
    
    # Lead actions
    path("dashboard/leads/<int:pk>/toggle-read/", views.toggle_lead_read_view, name="toggle_lead_read"),
    path("dashboard/leads/<int:pk>/toggle-archive/", views.toggle_lead_archive_view, name="toggle_lead_archive"),
    path("dashboard/leads/<int:pk>/mark-read/", views.mark_lead_read_view, name="mark_lead_read"),
]
