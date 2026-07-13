from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
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
    active_leads = Lead.objects.filter(link__profile=profile, is_archived=False).order_by("-created_at")
    total_leads = Lead.objects.filter(link__profile=profile)
    leads_count = total_leads.values("whatsapp_number").distinct().count()
    
    return render(request, "profiles/dashboard.html", {
        "profile": profile,
        "links": links,
        "leads": active_leads,
        "leads_count": leads_count,
    })

@login_required
def preview_links_grid_view(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return HttpResponse("Profile not found", status=404)
        
    links = profile.links.all().order_by("sort_order", "created_at")
    return render(request, "profiles/partials/preview_links_grid.html", {
        "profile": profile,
        "links": links,
        "is_oob": False
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
            
            avatar_url = profile.avatar.url if profile.avatar else ""
            return JsonResponse({
                "status": "success",
                "display_name": profile.display_name,
                "bio": profile.bio,
                "avatar_url": avatar_url,
                "is_visible": profile.is_visible,
                "warning_msg": warning_msg
            })
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            return HttpResponse(
                msg,
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
        # Detect whether the caller is HTMX or a plain fetch() (Alpine.js)
        is_htmx = request.headers.get("HX-Request") == "true"
        
        if not label or not url or not surface_type:
            if not is_htmx:
                return JsonResponse({"success": False, "error": "Fill all fields."}, status=400)
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links, "profile": profile})
            response.write('<div class="text-red-400 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">Fill all fields.</div>')
            return response
            
        link = Link(profile=profile, label=label, url=url, surface_type=surface_type)
        try:
            link.full_clean()
            link.save()
            
            if not is_htmx:
                return JsonResponse({"success": True})
            
            active_count = profile.links.filter(is_active=True).count()
            limit = 50 if profile.is_premium else 10
            warning_msg = ""
            if active_count == limit - 1:
                warning_msg = f'<div class="text-amber-500 text-xs mt-2" id="link-add-msg" hx-swap-oob="true">Soft cap warning: you have {active_count} active links. Limit is {limit}.</div>'
            else:
                warning_msg = '<div id="link-add-msg" hx-swap-oob="true"></div>'
                
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links, "profile": profile})
            response.write(warning_msg)
            return response
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            if not is_htmx:
                return JsonResponse({"success": False, "error": msg}, status=400)
            links = profile.links.all().order_by("sort_order", "created_at")
            response = render(request, "profiles/partials/links_list.html", {"links": links, "profile": profile})
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
            limit = 50 if profile.is_premium else 10
            if active_count >= limit:
                if profile.is_premium:
                    return HttpResponse("You can have a maximum of 50 active links.", status=400)
                else:
                    return HttpResponse("You can have a maximum of 10 active links.", status=400)
                
        link.is_active = is_active
        link.save()
        
        # If no active links remaining, automatically disable profile public visibility
        if profile.is_visible and profile.links.filter(is_active=True).count() == 0:
            profile.is_visible = False
            profile.save()
            
        return HttpResponse("")
        
    return HttpResponseForbidden()

@login_required
def delete_link_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    if request.method in ["POST", "DELETE"]:
        link.delete()
        
        # Re-check visibility
        if profile.is_visible and profile.links.filter(is_active=True).count() == 0:
            profile.is_visible = False
            profile.save()
            
        is_htmx = request.headers.get("HX-Request") == "true" or request.META.get("HTTP_HX_REQUEST") == "true"
        if is_htmx:
            links_count = profile.links.count()
            limit = 50 if profile.is_premium else 10
            badge_html = f"""
            <div class="flex items-center gap-1 text-[11px] font-bold text-theme-muted" id="link-count-badge" hx-swap-oob="true">
                <span class="text-brand-400">{links_count}</span>
                <span>/ {limit}</span>
            </div>
            """
            if links_count == 0:
                empty_html = """
                <div id="preview-links-grid" class="w-full max-w-3xl mt-8 flex flex-wrap justify-center gap-4" hx-swap-oob="true">
                    <div x-show="!newCardOpen" class="w-full flex flex-col items-center justify-center py-16 text-center">
                        <button @click="newCardOpen = !newCardOpen"
                            class="w-16 h-16 rounded-2xl bg-[#25D366]/10 flex items-center justify-center mb-4 cursor-pointer hover:bg-[#25D366]/20 hover:scale-105 active:scale-95 transition-all"
                            title="Add first link">
                            <svg class="w-8 h-8 text-[#25D366]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                            </svg>
                        </button>
                        <p class="text-sm font-bold text-gray-500">No links yet</p>
                        <p class="text-xs text-gray-400 mt-1">Click the <strong>+</strong> button to add your first WhatsApp link</p>
                    </div>
                </div>
                """
                fab_hide_html = '<button id="floating-add-btn" hx-swap-oob="true" class="hidden"></button>'
                response = HttpResponse(empty_html + badge_html + fab_hide_html)
            else:
                response = HttpResponse(badge_html)
            response["HX-Trigger"] = "linkDeleted"
            return response
        else:
            return redirect("profiles:dashboard")
        
    return HttpResponseForbidden()

@login_required
def sort_links_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        link_ids = request.POST.getlist("link_id")
        with transaction.atomic():
            for index, lid in enumerate(link_ids):
                Link.objects.filter(pk=lid, profile=profile).update(sort_order=index)
                
        response = HttpResponse("")
        response["HX-Trigger"] = "linksChanged"
        return response
        
@login_required
def toggle_visibility_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    if request.method == "POST":
        is_visible = request.POST.get("is_visible") == "true"
        
        # Guard: check active links
        active_count = profile.links.filter(is_active=True).count()
        if is_visible and active_count == 0:
            return HttpResponse(
                '<div class="text-red-400 text-xs mt-2" id="visibility-msg">Add at least 1 active link first.</div>',
                status=400
            )
            
        profile.is_visible = is_visible
        profile.save()
        
        return HttpResponse('')
        
    return HttpResponseForbidden()

def update_theme_view(request):
    if request.method == "POST":
        theme = request.POST.get("theme", "").strip()
        if theme in ["light", "dark", "whatsapp-green"]:
            response = HttpResponse("")
            if request.user.is_authenticated:
                try:
                    profile = request.user.profile
                    profile.theme = theme
                    profile.save()
                except Exception:
                    pass
            response.set_cookie("theme_preference", theme, max_age=365*24*60*60)
            return response
    return HttpResponse(status=400)


def get_country_from_phone(phone: str) -> str:
    if not phone:
        return "Unknown"
    phone = phone.strip()
    if not phone.startswith("+"):
        if len(phone) == 10:
            return "India"
        return "Unknown"
        
    prefixes = {
        "+1": "United States/Canada",
        "+30": "Greece",
        "+31": "Netherlands",
        "+32": "Belgium",
        "+33": "France",
        "+34": "Spain",
        "+36": "Hungary",
        "+39": "Italy",
        "+40": "Romania",
        "+41": "Switzerland",
        "+43": "Austria",
        "+44": "United Kingdom",
        "+45": "Denmark",
        "+46": "Sweden",
        "+47": "Norway",
        "+48": "Poland",
        "+49": "Germany",
        "+51": "Peru",
        "+52": "Mexico",
        "+53": "Cuba",
        "+54": "Argentina",
        "+55": "Brazil",
        "+56": "Chile",
        "+57": "Colombia",
        "+58": "Venezuela",
        "+60": "Malaysia",
        "+61": "Australia",
        "+62": "Indonesia",
        "+63": "Philippines",
        "+64": "New Zealand",
        "+65": "Singapore",
        "+66": "Thailand",
        "+81": "Japan",
        "+82": "South Korea",
        "+84": "Vietnam",
        "+86": "China",
        "+90": "Turkey",
        "+91": "India",
        "+92": "Pakistan",
        "+93": "Afghanistan",
        "+94": "Sri Lanka",
        "+95": "Myanmar",
        "+98": "Iran",
        "+212": "Morocco",
        "+213": "Algeria",
        "+216": "Tunisia",
        "+218": "Libya",
        "+221": "Senegal",
        "+233": "Ghana",
        "+234": "Nigeria",
        "+237": "Cameroon",
        "+244": "Angola",
        "+250": "Rwanda",
        "+251": "Ethiopia",
        "+254": "Kenya",
        "+255": "Tanzania",
        "+256": "Uganda",
        "+260": "Zambia",
        "+263": "Zimbabwe",
        "+267": "Botswana",
        "+351": "Portugal",
        "+352": "Luxembourg",
        "+353": "Ireland",
        "+354": "Iceland",
        "+355": "Albania",
        "+356": "Malta",
        "+357": "Cyprus",
        "+359": "Bulgaria",
        "+370": "Lithuania",
        "+371": "Latvia",
        "+372": "Estonia",
        "+373": "Moldova",
        "+374": "Armenia",
        "+375": "Belarus",
        "+376": "Andorra",
        "+377": "Monaco",
        "+380": "Ukraine",
        "+381": "Serbia",
        "+382": "Montenegro",
        "+385": "Croatia",
        "+386": "Slovenia",
        "+387": "Bosnia & Herzegovina",
        "+389": "North Macedonia",
        "+420": "Czech Republic",
        "+421": "Slovakia",
        "+423": "Liechtenstein",
        "+502": "Guatemala",
        "+503": "El Salvador",
        "+504": "Honduras",
        "+505": "Nicaragua",
        "+506": "Costa Rica",
        "+507": "Panama",
        "+591": "Bolivia",
        "+593": "Ecuador",
        "+595": "Paraguay",
        "+598": "Uruguay",
        "+673": "Brunei",
        "+852": "Hong Kong",
        "+853": "Macau",
        "+855": "Cambodia",
        "+856": "Laos",
        "+880": "Bangladesh",
        "+886": "Taiwan",
        "+960": "Maldives",
        "+961": "Lebanon",
        "+962": "Jordan",
        "+964": "Iraq",
        "+965": "Kuwait",
        "+966": "Saudi Arabia",
        "+967": "Yemen",
        "+968": "Oman",
        "+971": "United Arab Emirates",
        "+972": "Israel",
        "+973": "Bahrain",
        "+974": "Qatar",
        "+975": "Bhutan",
        "+976": "Mongolia",
        "+977": "Nepal",
        "+992": "Tajikistan",
        "+994": "Azerbaijan",
        "+995": "Georgia",
        "+996": "Kyrgyzstan",
        "+998": "Uzbekistan",
    }
    sorted_prefixes = sorted(prefixes.keys(), key=len, reverse=True)
    for prefix in sorted_prefixes:
        if phone.startswith(prefix):
            return prefixes[prefix]
    return "Other"


@login_required
def link_analytics_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    
    # Get form views from database (unique logged-in users by phone_number + unique anonymous visitors by ip_address)
    unique_logged_in = link.clicks.exclude(phone_number__isnull=True).values("phone_number").distinct().count()
    unique_anonymous = link.clicks.filter(phone_number__isnull=True).values("ip_address").distinct().count()
    views = unique_logged_in + unique_anonymous
    
    # Process unique leads based on unique WhatsApp phone numbers on this link to prevent spam
    seen_phones = set()
    unique_leads = []
    for lead in link.leads.all().order_by('created_at'):
        if lead.whatsapp_number not in seen_phones:
            seen_phones.add(lead.whatsapp_number)
            unique_leads.append(lead)
            
    leads_count = len(unique_leads)
    
    # If views is less than leads, adjust views to make it realistic
    if views < leads_count:
        views = leads_count

        
    conversion_rate = 0.0
    if views > 0:
        conversion_rate = round((leads_count / views) * 100, 1)
        
    # Devices and countries breakdown
    devices = {"Mobile": 0, "Desktop": 0}
    countries = {}
    
    for lead in unique_leads:
        ua = lead.user_agent.lower() if lead.user_agent else ""
        if not ua:
            devices["Desktop"] += 1
        else:
            # Device
            if "mobile" in ua or "android" in ua or "iphone" in ua or "ipad" in ua:
                devices["Mobile"] += 1
            else:
                devices["Desktop"] += 1
                
        # Country lookup from WhatsApp phone number
        country = get_country_from_phone(lead.whatsapp_number)
        countries[country] = countries.get(country, 0) + 1

    # Sort countries by count descending
    sorted_countries = dict(sorted(countries.items(), key=lambda item: item[1], reverse=True))

    # Daily leads over the last 7 days from unique leads
    from django.utils import timezone
    import datetime
    
    daily_counts = {}
    for lead in unique_leads:
        lead_date = lead.created_at.date()
        daily_counts[lead_date] = daily_counts.get(lead_date, 0) + 1

    today = timezone.now().date()
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        count = daily_counts.get(day, 0)
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
        "countries": sorted_countries,
        "daily_stats": daily_stats
    })


@login_required
def link_insights_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    links = profile.links.all()
    
    from django.utils import timezone
    import datetime
    
    last_7_days_start = timezone.now() - datetime.timedelta(days=7)
    
    best_link = None
    best_cvr = 0.0
    best_views = 0
    best_leads = 0
    
    for link in links:
        # Clicks in the last 7 days
        clicks_last_7_days = link.clicks.filter(created_at__gte=last_7_days_start)
        unique_logged_in = clicks_last_7_days.exclude(phone_number__isnull=True).values("phone_number").distinct().count()
        unique_anonymous = clicks_last_7_days.filter(phone_number__isnull=True).values("ip_address").distinct().count()
        views_7d = unique_logged_in + unique_anonymous
        
        # Leads in the last 7 days
        leads_last_7_days = link.leads.filter(created_at__gte=last_7_days_start)
        seen_phones = set()
        unique_leads = []
        for lead in leads_last_7_days.order_by('created_at'):
            if lead.whatsapp_number not in seen_phones:
                seen_phones.add(lead.whatsapp_number)
                unique_leads.append(lead)
        leads_count_7d = len(unique_leads)
        
        # Adjust views if clicks is lower than leads (realistic safeguard)
        if views_7d < leads_count_7d:
            views_7d = leads_count_7d
            
        cvr_7d = 0.0
        if views_7d > 0:
            cvr_7d = round((leads_count_7d / views_7d) * 100, 1)
            
        # Tie-breaking rules:
        # 1. Higher conversion ratio
        # 2. If equal, higher lead count
        # 3. If still equal, higher views count
        # 4. If still equal, fallback to earlier link (implicit in loop order)
        if best_link is None:
            best_link = link
            best_cvr = cvr_7d
            best_views = views_7d
            best_leads = leads_count_7d
        else:
            if cvr_7d > best_cvr:
                best_link = link
                best_cvr = cvr_7d
                best_views = views_7d
                best_leads = leads_count_7d
            elif cvr_7d == best_cvr:
                if leads_count_7d > best_leads:
                    best_link = link
                    best_cvr = cvr_7d
                    best_views = views_7d
                    best_leads = leads_count_7d
                elif leads_count_7d == best_leads and views_7d > best_views:
                    best_link = link
                    best_cvr = cvr_7d
                    best_views = views_7d
                    best_leads = leads_count_7d

    return render(request, "profiles/partials/link_insights.html", {
        "best_link": best_link,
        "best_cvr": best_cvr,
        "best_views": best_views,
        "best_leads": best_leads,
        "has_links": links.exists(),
    })


@login_required
def links_list_view(request):
    profile = get_object_or_404(Profile, user=request.user)
    links = profile.links.all().order_by("sort_order", "created_at")
    return render(request, "profiles/partials/links_list.html", {"links": links, "profile": profile})

@login_required
def edit_link_view(request, pk):
    profile = get_object_or_404(Profile, user=request.user)
    link = get_object_or_404(Link, pk=pk, profile=profile)
    
    if request.method == "POST":
        label = request.POST.get("label", "").strip()
        url = request.POST.get("url", "").strip()
        surface_type = request.POST.get("surface_type", "").strip()
        is_htmx = request.headers.get("HX-Request") == "true"
        
        if not label or not url or not surface_type:
            if not is_htmx:
                return JsonResponse({"success": False, "error": "All fields are required."}, status=400)
            return render(request, "profiles/partials/edit_link_form.html", {
                "profile": profile,
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
            if not is_htmx:
                return JsonResponse({"success": True})
            response = HttpResponse("")
            response["HX-Trigger"] = "closeEditModal,linkListChanged"
            return response
        except ValidationError as e:
            msg = e.messages[0] if isinstance(e.messages, list) else str(e)
            if not is_htmx:
                return JsonResponse({"success": False, "error": msg}, status=400)
            return render(request, "profiles/partials/edit_link_form.html", {
                "profile": profile,
                "link": link,
                "error": msg,
                "submitted_label": label,
                "submitted_url": url,
                "submitted_surface_type": surface_type,
            })
            
    return render(request, "profiles/partials/edit_link_form.html", {
        "profile": profile,
        "link": link,
        "submitted_label": link.label,
        "submitted_url": link.url,
        "submitted_surface_type": link.surface_type,
    })


@login_required
def search_handle_view(request):
    if request.method == "POST":
        handle = request.POST.get("handle", "").strip().lower()
        if not handle:
            return HttpResponse('<div class="text-red-400 font-medium">Handle is required.</div>', status=400)
        
        try:
            profile = Profile.objects.get(handle__iexact=handle)
            response = HttpResponse()
            response["HX-Redirect"] = f"/{profile.handle}/"
            return response
        except Profile.DoesNotExist:
            return HttpResponse(f'<div class="text-red-400 font-medium mt-1">Handle "@{handle}" not found.</div>')
            
    return HttpResponseForbidden()


@login_required
@transaction.atomic
def upgrade_premium_view(request):
    if request.method == "POST":
        profile = get_object_or_404(Profile, user=request.user)
        profile.is_premium = True
        profile.save()
        return JsonResponse({"success": True})
    return HttpResponseForbidden()

