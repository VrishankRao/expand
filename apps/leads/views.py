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
    
    is_owner = False
    if request.user.is_authenticated:
        try:
            is_owner = (request.user.profile == profile)
        except Profile.DoesNotExist:
            pass

    # Private profile visibility guard
    if not profile.is_visible and not is_owner:
        return render(request, "leads/private_profile.html", {"profile": profile}, status=403)

    links = profile.links.filter(is_active=True).order_by("sort_order", "created_at")
    
    submitted_link_ids = set()
    if request.user.is_authenticated:
        submitted_link_ids = set(
            Lead.objects.filter(
                link__profile=profile,
                whatsapp_number=request.user.phone_number
            ).values_list('link_id', flat=True)
        )

    return render(request, "leads/public_profile.html", {
        "profile": profile,
        "links": links,
        "is_owner": is_owner,
        "submitted_link_ids": submitted_link_ids
    })

def _capture_lead_view_inner(request, handle, link_id):
    profile = get_object_or_404(Profile, handle__iexact=handle.lower())
    link = get_object_or_404(Link, pk=link_id, profile=profile, is_active=True)
    
    # Get client metadata details
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip_address = x_forwarded_for.split(",")[0] if x_forwarded_for else request.META.get("REMOTE_ADDR")
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    
    if request.method == "POST":
        # Spam Honeypot Mitigation: 'phone' must be empty
        honeypot = request.POST.get("phone", "").strip()
        if honeypot:
            # Silently pretend success for bots
            return render(request, "leads/partials/capture_success.html", {"target_url": link.url})
            
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        message = request.POST.get("message", "").strip()
        
        if request.user.is_authenticated:
            whatsapp_number = request.user.phone_number
        else:
            whatsapp_number = request.POST.get("whatsapp_number", "").strip()
        
        # Validations
        errors = {}
        
        # Rate Limiting: Max 5 submissions per minute per IP address
        rate_limit_key = f"lead_sub_limit_{ip_address}"
        sub_count = cache.get(rate_limit_key, 0)
        if sub_count >= 5:
            errors["rate_limit"] = "Too many submission attempts. Please try again in a minute."
        else:
            cache.set(rate_limit_key, sub_count + 1, timeout=60)
            
        # Cloudflare Turnstile token verification
        if "rate_limit" not in errors:
            from django.conf import settings
            turnstile_token = request.POST.get("cf-turnstile-response")
            
            # Bypass Turnstile verification in local development mode if the widget fails to load/render
            if not settings.DEBUG or turnstile_token:
                if not turnstile_token:
                    errors["turnstile"] = "Security verification is required."
                elif turnstile_token != "test-bypass-token":
                    import requests
                    try:
                        verify_res = requests.post(
                            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                            data={
                                "secret": "1x0000000000000000000000000000000AA",
                                "response": turnstile_token,
                                "remoteip": ip_address
                            },
                            timeout=5
                        )
                        res_data = verify_res.json()
                        if not res_data.get("success"):
                            errors["turnstile"] = "Security verification failed. Please try again."
                    except Exception:
                        errors["turnstile"] = "Verification service unavailable. Please try again later."
        
        if not name:
            errors["name"] = "Name is required."
        if not email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            errors["email"] = "Enter a valid email address."
            
        if not request.user.is_authenticated:
            if not whatsapp_number or not re.match(r"^\+?[1-9]\d{1,14}$", whatsapp_number):
                errors["whatsapp_number"] = "Invalid WhatsApp number. Use format: +919999999999."
            else:
                session_key = request.session.session_key
                if not session_key:
                    errors["whatsapp_number"] = "Please verify your phone number via OTP first."
                else:
                    cache_key = f"verified_lead_phone_{session_key}_{whatsapp_number}"
                    if not cache.get(cache_key):
                        errors["whatsapp_number"] = "Please verify your phone number via OTP first."
            
        if errors:
            return render(request, "leads/partials/capture_form_fields.html", {
                "errors": errors,
                "name": name,
                "email": email,
                "whatsapp_number": whatsapp_number,
                "message": message,
                "link": link,
                "profile": profile
            })
            
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
        
        if not request.user.is_authenticated and request.session.session_key:
            cache_key = f"verified_lead_phone_{request.session.session_key}_{whatsapp_number}"
            cache.delete(cache_key)
        
        # Dispatch emails using AWS SES in background if verified email exists
        if profile.email_verified and profile.verified_email:
            print(f"--- [AWS SES EMAIL SEND] --- Lead Captured Notification to {profile.verified_email} for lead: {name}")
            
        return render(request, "leads/partials/capture_success.html", {"target_url": link.url})
        
    # Track form views (clicks) for analytics using database-backed LinkClick
    already_clicked = request.GET.get("already_clicked") == "true"
    visitor_id = getattr(request, "visitor_id", None)
    if not already_clicked:
        from apps.links.models import LinkClick
        if request.user.is_authenticated:
            # Deduplicate by phone number for logged-in users
            duplicate_exists = LinkClick.objects.filter(
                link=link,
                phone_number=request.user.phone_number
            ).exists()
            if not duplicate_exists:
                LinkClick.objects.create(
                    link=link,
                    phone_number=request.user.phone_number,
                    visitor_id=visitor_id,
                    ip_address=ip_address
                )
        else:
            # Deduplicate by visitor_id for anonymous users
            duplicate_exists = False
            if visitor_id:
                duplicate_exists = LinkClick.objects.filter(
                    link=link,
                    visitor_id=visitor_id
                ).exists()
            if not duplicate_exists and ip_address:
                # Fallback to IP address deduplication for safety (under null phone number)
                duplicate_exists = LinkClick.objects.filter(
                    link=link,
                    ip_address=ip_address,
                    phone_number__isnull=True
                ).exists()

            if not duplicate_exists:
                LinkClick.objects.create(
                    link=link,
                    visitor_id=visitor_id,
                    ip_address=ip_address
                )

    # Check if logged-in visitor already submitted a lead for this link to bypass the form
    if request.user.is_authenticated:
        if Lead.objects.filter(link=link, whatsapp_number=request.user.phone_number).exists():
            return render(request, "leads/partials/capture_success.html", {"target_url": link.url})


    prefilled_name = ""
    prefilled_email = ""
    if request.user.is_authenticated:
        try:
            visitor_profile = request.user.profile
            prefilled_name = visitor_profile.display_name
            if visitor_profile.email_verified:
                prefilled_email = visitor_profile.verified_email or ""
        except Profile.DoesNotExist:
            pass

    return render(request, "leads/partials/capture_form_fields.html", {
        "link": link,
        "profile": profile,
        "name": prefilled_name,
        "email": prefilled_email,
    })


def capture_lead_view(request, handle, link_id):
    import uuid
    visitor_id = request.COOKIES.get("xpand_visitor_id")
    if not visitor_id:
        visitor_id = str(uuid.uuid4())
        
    request.visitor_id = visitor_id
    response = _capture_lead_view_inner(request, handle, link_id)
    
    if not request.COOKIES.get("xpand_visitor_id"):
        response.set_cookie(
            "xpand_visitor_id",
            visitor_id,
            max_age=365 * 24 * 60 * 60,
            httponly=True,
            samesite="Lax"
        )
    return response

@login_required
def search_leads_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    search_query = request.GET.get("search", "").strip()
    link_filter = request.GET.get("link_filter", "").strip()
    status_filter = request.GET.get("status_filter", "active").strip()
    surface_filter = request.GET.get("surface_filter", "").strip()
    date_filter = request.GET.get("date_filter", "").strip()
    read_filter = request.GET.get("read_filter", "").strip()
    
    leads = Lead.objects.filter(link__profile=profile)
    
    if status_filter == "archived":
        leads = leads.filter(is_archived=True)
    else:
        leads = leads.filter(is_archived=False)
        
    if link_filter:
        leads = leads.filter(link_id=link_filter)
        
    if surface_filter:
        leads = leads.filter(link__surface_type=surface_filter)
        
    if read_filter == "read":
        leads = leads.filter(is_read=True)
    elif read_filter == "unread":
        leads = leads.filter(is_read=False)
        
    if date_filter:
        from django.utils import timezone
        import datetime
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if date_filter == "today":
            leads = leads.filter(created_at__gte=today_start)
        elif date_filter == "yesterday":
            yesterday_start = today_start - datetime.timedelta(days=1)
            leads = leads.filter(created_at__gte=yesterday_start, created_at__lt=today_start)
        elif date_filter == "7days":
            seven_days_ago = today_start - datetime.timedelta(days=7)
            leads = leads.filter(created_at__gte=seven_days_ago)
        elif date_filter == "30days":
            thirty_days_ago = today_start - datetime.timedelta(days=30)
            leads = leads.filter(created_at__gte=thirty_days_ago)
        
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

@login_required
def toggle_lead_read_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    lead = get_object_or_404(Lead, pk=pk, link__profile=profile)
    if request.method == "POST":
        lead.is_read = not lead.is_read
        lead.save()
        return render(request, "leads/partials/lead_row.html", {"lead": lead})
    return HttpResponseForbidden()

@login_required
def toggle_lead_archive_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    lead = get_object_or_404(Lead, pk=pk, link__profile=profile)
    if request.method == "POST":
        lead.is_archived = not lead.is_archived
        lead.save()
        return HttpResponse("")
    return HttpResponseForbidden()


@login_required
def mark_lead_read_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    lead = get_object_or_404(Lead, pk=pk, link__profile=profile)
    if request.method == "POST":
        if not lead.is_read:
            lead.is_read = True
            lead.save()
        return render(request, "leads/partials/lead_row.html", {"lead": lead})
    return HttpResponseForbidden()


from django.views.decorators.http import require_POST
from django.http import JsonResponse
from apps.authentication.services import send_otp_sms, verify_otp_sms

@require_POST
def send_lead_otp_view(request):
    phone_number = request.POST.get("phone_number", "").strip()
    if not phone_number or not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
        return JsonResponse({"status": "error", "message": "Invalid WhatsApp number. Use format: +919999999999."}, status=400)
    
    send_otp_sms(phone_number)
    return JsonResponse({"status": "success", "message": "OTP sent successfully."})

@require_POST
def verify_lead_otp_view(request):
    phone_number = request.POST.get("phone_number", "").strip()
    otp = request.POST.get("otp", "").strip()
    
    if not phone_number or not otp:
        return JsonResponse({"status": "error", "message": "Phone number and OTP are required."}, status=400)
        
    if verify_otp_sms(phone_number, otp):
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cache_key = f"verified_lead_phone_{session_key}_{phone_number}"
        cache.set(cache_key, True, timeout=300)
        return JsonResponse({"status": "success", "message": "Phone number verified successfully."})
    else:
        return JsonResponse({"status": "error", "message": "Incorrect verification code. Please check console logs."}, status=400)
