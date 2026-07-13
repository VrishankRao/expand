from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.views.decorators.http import require_POST
from functools import wraps
from django.urls import reverse
import re


def clean_phone_number(phone_number: str) -> str:
    phone = phone_number.strip()
    if phone.isdigit() and len(phone) == 10:
        phone = f"+91{phone}"
    return phone


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect(reverse("admin_panel:login"))
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("admin_panel:dashboard")

    error_msg = ""
    phone_init = request.GET.get("phone", "")
    if phone_init.startswith("+91"):
        phone_init = phone_init[3:]
    phone_init = re.sub(r"\D", "", phone_init)[:10]

    if request.method == "POST":
        phone_number = clean_phone_number(request.POST.get("phone_number", ""))
        password = request.POST.get("password", "")

        user = authenticate(request, username=phone_number, password=password)
        if user is not None:
            if user.is_staff:
                login(request, user)
                return redirect("admin_panel:dashboard")
            else:
                error_msg = "Access Denied. Admins only."
        else:
            error_msg = "Invalid phone number or password."

    return render(request, "admin_panel/login.html", {
        "phone_init": phone_init,
        "error_msg": error_msg
    })


def admin_logout_view(request):
    logout(request)
    return redirect("admin_panel:login")


@admin_required
def admin_dashboard_view(request):
    from apps.profiles.models import Profile
    User = get_user_model()

    total_users = Profile.objects.count()
    premium_users = Profile.objects.filter(is_premium=True).count()
    free_users = Profile.objects.filter(is_premium=False).count()

    profiles = Profile.objects.select_related('user').all().order_by('-created_at')

    return render(request, "admin_panel/dashboard.html", {
        "total_users": total_users,
        "premium_users": premium_users,
        "free_users": free_users,
        "profiles": profiles
    })


@admin_required
def admin_user_detail_view(request, handle):
    from apps.profiles.models import Profile
    from apps.leads.models import Lead
    from django.db.models import Count

    profile = get_object_or_404(Profile.objects.select_related('user'), handle=handle)
    links = (
        profile.links.all()
        .annotate(
            click_count=Count('clicks', distinct=True),
            lead_count=Count('leads', distinct=True),
        )
        .order_by("sort_order", "created_at")
    )

    total_leads = Lead.objects.filter(link__profile=profile)
    leads_count = total_leads.values("whatsapp_number").distinct().count()

    return render(request, "admin_panel/user_detail.html", {
        "profile": profile,
        "links": links,
        "leads_count": leads_count
    })


@admin_required
@require_POST
def admin_toggle_visibility_view(request, handle):
    from apps.profiles.models import Profile

    profile = get_object_or_404(Profile, handle=handle)
    val = request.POST.get("is_visible") == "true"
    profile.is_visible = val
    profile.save()
    return render(request, "admin_panel/partials/visibility_toggle.html", {"profile": profile})


@admin_required
@require_POST
def admin_delete_user_view(request, handle):
    from apps.profiles.models import Profile

    profile = get_object_or_404(Profile, handle=handle)
    user = profile.user
    user.delete()  # cascades to Profile and all related data
    return redirect("admin_panel:dashboard")


@admin_required
def admin_link_analytics_view(request, pk):
    from apps.links.models import Link
    from apps.profiles.views import get_country_from_phone
    from django.utils import timezone
    import datetime

    link = get_object_or_404(Link, pk=pk)

    unique_logged_in = link.clicks.exclude(phone_number__isnull=True).values("phone_number").distinct().count()
    unique_anonymous = link.clicks.filter(phone_number__isnull=True).values("ip_address").distinct().count()
    views = unique_logged_in + unique_anonymous

    seen_phones = set()
    unique_leads = []
    for lead in link.leads.all().order_by('created_at'):
        if lead.whatsapp_number not in seen_phones:
            seen_phones.add(lead.whatsapp_number)
            unique_leads.append(lead)

    leads_count = len(unique_leads)

    if views < leads_count:
        views = leads_count

    conversion_rate = 0.0
    if views > 0:
        conversion_rate = round((leads_count / views) * 100, 1)

    devices = {"Mobile": 0, "Desktop": 0}
    countries = {}

    for lead in unique_leads:
        ua = lead.user_agent.lower() if lead.user_agent else ""
        if not ua or ("mobile" not in ua and "android" not in ua and "iphone" not in ua and "ipad" not in ua):
            devices["Desktop"] += 1
        else:
            devices["Mobile"] += 1
        country = get_country_from_phone(lead.whatsapp_number)
        countries[country] = countries.get(country, 0) + 1

    sorted_countries = dict(sorted(countries.items(), key=lambda item: item[1], reverse=True))

    daily_counts = {}
    for lead in unique_leads:
        lead_date = lead.created_at.date()
        daily_counts[lead_date] = daily_counts.get(lead_date, 0) + 1

    today = timezone.now().date()
    daily_stats = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        daily_stats.append({"date": day.strftime("%b %d"), "count": daily_counts.get(day, 0)})

    return render(request, "profiles/partials/link_analytics.html", {
        "link": link,
        "views": views,
        "leads_count": leads_count,
        "conversion_rate": conversion_rate,
        "devices": devices,
        "countries": sorted_countries,
        "daily_stats": daily_stats,
    })
