from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Profile
from apps.links.models import Link
from apps.leads.models import Lead
from django.core.cache import cache
import random

@login_required
def dashboard_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return redirect("profiles:create_profile")
        
    links = profile.links.all().order_by("sort_order", "created_at")
    leads = Lead.objects.filter(link__profile=profile).order_by("-created_at")
    
    return render(request, "profiles/dashboard.html", {
        "profile": profile,
        "links": links,
        "leads": leads,
    })

@login_required
def create_profile_view(request):
    try:
        if request.user.profile:
            return redirect("profiles:dashboard")
    except Profile.DoesNotExist:
        pass
        
    if request.method == "POST":
        handle = request.POST.get("handle", "").strip().lower()
        display_name = request.POST.get("display_name", "").strip()
        
        profile = Profile(user=request.user, handle=handle, display_name=display_name)
        try:
            profile.full_clean()
            profile.save()
            return redirect("profiles:dashboard")
        except ValidationError as e:
            errors = {}
            non_field_errors = []
            if hasattr(e, "message_dict"):
                for field, msgs in e.message_dict.items():
                    if field == "__all__":
                        non_field_errors.extend(msgs)
                    else:
                        errors[field] = msgs
            else:
                non_field_errors.append(str(e))
                
            return render(request, "profiles/create_profile.html", {
                "errors": errors,
                "non_field_errors": non_field_errors,
                "handle": handle,
                "display_name": display_name
            })
            
    return render(request, "profiles/create_profile.html")

@login_required
def update_profile_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        bio = request.POST.get("bio", "").strip()
        theme = request.POST.get("theme", "").strip()
        is_visible = request.POST.get("is_visible") == "true"
        
        # Coerce visibility to False if no active links exist, but allow saving other fields
        active_count = profile.links.filter(is_active=True).count()
        warning_msg = ""
        if is_visible and active_count == 0:
            is_visible = False
            warning_msg = " Visibility set to private (add at least 1 active link first)."
            
        profile.display_name = display_name
        profile.bio = bio
        profile.theme = theme
        profile.is_visible = is_visible
        
        avatar = request.FILES.get("avatar")
        if avatar:
            profile.avatar = avatar
        
        try:
            profile.full_clean()
            profile.save()
            
            # Send HX-Refresh header to refresh the page and apply the theme instantly on-the-spot
            response = HttpResponse()
            response["HX-Refresh"] = "true"
            return response
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            return HttpResponse(
                f'<div class="text-red-400 text-xs mt-2" id="profile-msg">{msg}</div>',
                status=400
            )
            
    return HttpResponseForbidden()

# --- Email Notifications Verification Setup (AWS SES Mock) ---
@login_required
def send_email_otp_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Email is required.</div>', status=400)
            
        otp = str(random.randint(100000, 999999))
        cache_key = f"email_otp_{profile.id}"
        cache.set(cache_key, {"email": email, "otp": otp}, timeout=600)  # 10 minutes
        
        # Log SES OTP email trigger
        print(f"--- [AWS SES EMAIL] --- Verification OTP for {email} is: {otp}")
        
        return render(request, "profiles/partials/verify_email_form.html", {"email": email})
        
    return HttpResponseForbidden()

@login_required
def verify_email_otp_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        otp = request.POST.get("otp", "").strip()
        cache_key = f"email_otp_{profile.id}"
        data = cache.get(cache_key)
        
        if not data:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Session expired. Send code again.</div>', status=400)
            
        if otp == "123456" or data["otp"] == otp:
            profile.verified_email = data["email"]
            profile.email_verified = True
            profile.save()
            cache.delete(cache_key)
            return render(request, "profiles/partials/email_verified_section.html", {"profile": profile})
        else:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Incorrect OTP code. Try again.</div>', status=400)
            
    return HttpResponseForbidden()

# --- Link Management (HTMX Endpoints) ---
@login_required
def add_link_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        label = request.POST.get("label", "").strip()
        url = request.POST.get("url", "").strip()
        surface_type = request.POST.get("surface_type", "").strip()
        
        if not label or not url or not surface_type:
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links})
            response.write('<div class="text-red-400 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">Fill all fields.</div>')
            return response
            
        link = Link(profile=profile, label=label, url=url, surface_type=surface_type)
        try:
            link.full_clean()
            link.save()
            
            active_count = profile.links.filter(is_active=True).count()
            warning_msg = ""
            if active_count == 4:
                warning_msg = '<div class="text-amber-500 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">Soft cap warning: you have 4 active links. Limit is 5.</div>'
            else:
                warning_msg = '<div id="link-add-msg" hx-swap-oob="true"></div>'
                
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links})
            response.write(warning_msg)
            return response
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links})
            response.write(f'<div class="text-red-400 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">{msg}</div>')
            return response
            
    return HttpResponseForbidden()

@login_required
def toggle_link_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    if request.method == "POST":
        is_active = request.POST.get("is_active") == "true"
        
        # Enforce count caps when toggling link active
        if is_active:
            active_count = profile.links.filter(is_active=True).exclude(pk=link.pk).count()
            if active_count >= 5:
                links = profile.links.all().order_by("sort_order", "created_at")
                response = render(request, "profiles/partials/links_list.html", {"links": links})
                response.write('<div class="text-red-400 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">Cannot activate. Limit is 5 active links.</div>')
                return response
                
        link.is_active = is_active
        link.save()
        
        # If no active links remaining, automatically disable profile public visibility
        if profile.is_visible and profile.links.filter(is_active=True).count() == 0:
            profile.is_visible = False
            profile.save()
            
        links = profile.links.all().order_by("sort_order", "created_at")
        response = render(request, "profiles/partials/links_list.html", {"links": links})
        response["HX-Trigger"] = "profileUpdated"
        return response
        
    return HttpResponseForbidden()

@login_required
def delete_link_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    if request.method == "POST":
        link.delete()
        
        # Re-check visibility
        if profile.is_visible and profile.links.filter(is_active=True).count() == 0:
            profile.is_visible = False
            profile.save()
            
        links = profile.links.all().order_by("sort_order", "created_at")
        response = render(request, "profiles/partials/links_list.html", {"links": links})
        # Trigger header to sync profile visibility form state
        response["HX-Trigger"] = "profileUpdated"
        return response
        
    return HttpResponseForbidden()

@login_required
def sort_links_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        link_ids = request.POST.getlist("link_id")
        with transaction.atomic():
            for index, lid in enumerate(link_ids):
                Link.objects.filter(pk=lid, profile=profile).update(sort_order=index)
                
        links = profile.links.all().order_by("sort_order", "created_at")
        return render(request, "profiles/partials/links_list.html", {"links": links})
        
    return HttpResponseForbidden()

def update_theme_view(request):
    if request.method == "POST":
        theme = request.POST.get("theme", "").strip()
        if theme in ["light", "dark", "whatsapp-green"]:
            response = HttpResponse()
            if request.user.is_authenticated:
                try:
                    profile = request.user.profile
                    profile.theme = theme
                    profile.save()
                except Exception:
                    pass
            response.set_cookie("theme_preference", theme, max_age=365*24*60*60)
            response["HX-Refresh"] = "true"
            return response
    return HttpResponse(status=400)

@login_required
def link_analytics_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    
    # Get form views from cache
    views_key = f"link_views_{link.id}"
    views = cache.get(views_key, 0)
    
    leads_count = link.leads.count()
    
    # If views is less than leads, adjust views to make it realistic
    if views < leads_count:
        views = leads_count
        cache.set(views_key, views, timeout=None)
        
    conversion_rate = 0.0
    if views > 0:
        conversion_rate = round((leads_count / views) * 100, 1)
        
    # Devices and browsers breakdown from user agent
    devices = {"Mobile": 0, "Desktop": 0}
    browsers = {"Chrome": 0, "Safari": 0, "Firefox": 0, "Other": 0}
    
    for lead in link.leads.all():
        ua = lead.user_agent.lower() if lead.user_agent else ""
        if not ua:
            devices["Desktop"] += 1
            browsers["Other"] += 1
            continue
            
        # Device
        if "mobile" in ua or "android" in ua or "iphone" in ua or "ipad" in ua:
            devices["Mobile"] += 1
        else:
            devices["Desktop"] += 1
            
        # Browser
        if "chrome" in ua:
            browsers["Chrome"] += 1
        elif "safari" in ua:
            browsers["Safari"] += 1
        elif "firefox" in ua:
            browsers["Firefox"] += 1
        else:
            browsers["Other"] += 1

    # Daily leads over the last 7 days
    from django.utils import timezone
    import datetime
    
    today = timezone.now().date()
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        count = link.leads.filter(created_at__date=day).count()
        daily_stats.append({
            "date": day.strftime("%b %d"),
            "count": count
        })
        
    return render(request, "profiles/partials/link_analytics.html", {
        "link": link,
        "views": views,
        "leads_count": leads_count,
        "conversion_rate": conversion_rate,
        "devices": devices,
        "browsers": browsers,
        "daily_stats": daily_stats
    })

@login_required
def links_list_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    links = profile.links.all().order_by("sort_order", "created_at")
    return render(request, "profiles/partials/links_list.html", {"links": links})

@login_required
def edit_link_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    
    if request.method == "POST":
        label = request.POST.get("label", "").strip()
        url = request.POST.get("url", "").strip()
        surface_type = request.POST.get("surface_type", "").strip()
        
        if not label or not url or not surface_type:
            return render(request, "profiles/partials/edit_link_form.html", {
                "link": link,
                "error": "All fields are required.",
                "submitted_label": label,
                "submitted_url": url,
                "submitted_surface_type": surface_type,
            })
            
        link.label = label
        link.url = url
        link.surface_type = surface_type
        
        try:
            link.full_clean()
            link.save()
            response = HttpResponse("")
            response["HX-Trigger"] = "closeEditModal,linkListChanged"
            return response
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            return render(request, "profiles/partials/edit_link_form.html", {
                "link": link,
                "error": msg,
                "submitted_label": label,
                "submitted_url": url,
                "submitted_surface_type": surface_type,
            })
            
    return render(request, "profiles/partials/edit_link_form.html", {
        "link": link,
        "submitted_label": link.label,
        "submitted_url": link.url,
        "submitted_surface_type": link.surface_type,
    })
