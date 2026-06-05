from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect

def root_redirect_view(request):
    if request.user.is_authenticated:
        return redirect("profiles:dashboard")
    return redirect("authentication:login")

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("apps.authentication.urls")),
    path("dashboard/", include("apps.profiles.urls")),
    path("", root_redirect_view, name="root_redirect"),
    path("", include("apps.leads.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
