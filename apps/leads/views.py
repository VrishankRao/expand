from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.db.models import Q
from apps.profiles.models import Profile
from apps.links.models import Link
from .models import Lead
from django.core.cache import cache
import csv
import re

def public_profile_view(request, handle):
    # Case-insensitive handle lookup
    profile = get_object_or_404(Profile, handle__iexact=handle.lower())
    
    # Private profile visibility guard
    if not profile.is_visible and (not request.user.is_authenticated or request.user.profile != profile):
        return render(request, "leads/private_profile.html", {"profile": profile}, status=403)
        
    is_owner = False
    if request.user.is_authenticated:
        try:
            is_owner = (request.user.profile == profile)
        except Profile.DoesNotExist:
            pass

    links = profile.links.filter(is_active=True).order_by("sort_order", "created_at")
    return render(request, "leads/public_profile.html", {
        "profile": profile,
        "links": links,
        "is_owner": is_owner
    })

def capture_lead_view(request, handle, link_id):
    profile = get_object_or_404(Profile, handle__iexact=handle.lower())
    link = get_object_or_404(Link, pk=link_id, profile=profile, is_active=True)
    
    if request.method == "POST":
        # Spam Honeypot Mitigation: 'phone' must be empty
        honeypot = request.POST.get("phone", "").strip()
        if honeypot:
            # Silently pretend success for bots
            return render(request, "leads/partials/capture_success.html", {"target_url": link.url})
            
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        whatsapp_number = request.POST.get("whatsapp_number", "").strip()
        message = request.POST.get("message", "").strip()
        
        # Validations
        errors = {}
        if not name:
            errors["name"] = "Name is required."
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors["email"] = "Enter a valid email address."
        if not whatsapp_number or not re.match(r"^\+?[1-9]\d{1,14}$", whatsapp_number):
            errors["whatsapp_number"] = "Invalid WhatsApp number. Use format: +919999999999."
            
        if errors:
            return render(request, "leads/partials/capture_form_fields.html", {
                "errors": errors,
                "name": name,
                "email": email,
                "whatsapp_number": whatsapp_number,
                "message": message,
                "link": link,
                "profile": profile
            }, status=400)
            
        # Capture metadata details
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        
        lead = Lead(
            link=link,
            name=name,
            email=email,
            whatsapp_number=whatsapp_number,
            message=message,
            ip_address=ip_address,
            user_agent=user_agent
        )
        lead.save()
        
        # Dispatch emails using AWS SES in background if verified email exists
        if profile.email_verified and profile.verified_email:
            print(f"--- [AWS SES EMAIL SEND] --- Lead Captured Notification to {profile.verified_email} for lead: {name}")
            
        return render(request, "leads/partials/capture_success.html", {"target_url": link.url})
        
    # Track form views (clicks) for analytics
    views_key = f"link_views_{link.id}"
    try:
        cache.incr(views_key)
    except ValueError:
        cache.set(views_key, 1, timeout=None)

    return render(request, "leads/partials/capture_form_fields.html", {
        "link": link,
        "profile": profile
    })

@login_required
def search_leads_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    search_query = request.GET.get("search", "").strip()
    link_filter = request.GET.get("link_filter", "").strip()
    
    leads = Lead.objects.filter(link__profile=profile)
    
    if link_filter:
        leads = leads.filter(link_id=link_filter)
        
    if search_query:
        leads = leads.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(whatsapp_number__icontains=search_query) |
            Q(message__icontains=search_query)
        )
        
    leads = leads.order_by("-created_at")
    return render(request, "leads/partials/leads_table_rows.html", {"leads": leads})

@login_required
def export_leads_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="leads.csv"'
    
    writer = csv.writer(response)
    writer.writerow(["Name", "Email", "WhatsApp Number", "CTA Label", "Surface Type", "Message", "IP Address", "Created At"])
    
    leads = Lead.objects.filter(link__profile=profile).order_by("-created_at")
    for lead in leads:
        writer.writerow([
            lead.name,
            lead.email,
            lead.whatsapp_number,
            lead.link_label_snapshot,
            lead.link.get_surface_type_display() if lead.link else "Deleted",
            lead.message,
            lead.ip_address,
            lead.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ])
        
    return response
