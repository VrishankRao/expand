from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, get_user_model
from django.http import HttpResponse
from .services import send_otp_sms, verify_otp_sms
import re

User = get_user_model()

def clean_phone_number(phone_number: str) -> str:
    phone = phone_number.strip()
    if phone.isdigit() and len(phone) == 10:
        phone = f"+91{phone}"
    return phone

def login_view(request):
    if request.user.is_authenticated:
        return redirect("profiles:dashboard")
        
    phone_init = request.GET.get("phone", "")
    if phone_init.startswith("+91"):
        phone_init = phone_init[3:]
    phone_init = re.sub(r"\D", "", phone_init)[:10]
        
    if request.method == "POST":
        phone_number = clean_phone_number(request.POST.get("phone_number", ""))
        
        # Validate E.164 phone number
        if not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
            response = HttpResponse('<div class="text-red-400 text-xs mt-2">Invalid format. Try "+919876543210".</div>')
            response["HX-Retarget"] = "#login-error"
            return response
            
        # Check if user exists
        if not User.objects.filter(phone_number=phone_number).exists():
            raw_phone = phone_number.replace("+91", "")
            response = HttpResponse(
                f'<div class="text-red-400 text-xs mt-2">'
                f'Phone number not registered. <a href="/auth/signup/?phone={raw_phone}" class="text-brand-500 font-bold hover:underline">Sign up with this number &rarr;</a>'
                f'</div>'
            )
            response["HX-Retarget"] = "#login-error"
            return response
            
        # Send SMS OTP
        send_otp_sms(phone_number)
        
        # Render OTP verification segment via HTMX
        return render(request, "authentication/verify_code.html", {"phone_number": phone_number})
        
    return render(request, "authentication/login.html", {"phone_init": phone_init})

def verify_view(request):
    if request.method == "POST":
        phone_number = clean_phone_number(request.POST.get("phone_number", ""))
        otp = request.POST.get("otp", "").strip()
        
        if not phone_number or not otp:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Required fields missing.</div>')
            
        if verify_otp_sms(phone_number, otp):
            user = get_object_or_404_user(phone_number)
            login(request, user)
            
            # Redirect straight to dashboard since profile is already set up
            response = HttpResponse()
            response["HX-Redirect"] = "/dashboard/"
            return response
        else:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Incorrect verification code. Please check console logs.</div>')
            
    return redirect("authentication:login")

def get_object_or_404_user(phone_number):
    try:
        return User.objects.get(phone_number=phone_number)
    except User.DoesNotExist:
        return None

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("profiles:dashboard")
        
    phone_init = request.GET.get("phone", "")
    if phone_init.startswith("+91"):
        phone_init = phone_init[3:]
    phone_init = re.sub(r"\D", "", phone_init)[:10]
        
    if request.method == "POST":
        phone_number = clean_phone_number(request.POST.get("phone_number", ""))
        
        # Validate E.164 phone number
        if not re.match(r"^\+?[1-9]\d{1,14}$", phone_number):
            response = HttpResponse('<div class="text-red-400 text-xs mt-2">Invalid format. Try "+919876543210".</div>')
            response["HX-Retarget"] = "#signup-error"
            return response
            
        # Check if user already exists
        if User.objects.filter(phone_number=phone_number).exists():
            raw_phone = phone_number.replace("+91", "")
            response = HttpResponse(
                f'<div class="text-red-400 text-xs mt-2">'
                f'Phone already registered. <a href="/auth/login/?phone={raw_phone}" class="text-brand-500 font-bold hover:underline">Log in with this number &rarr;</a>'
                f'</div>'
            )
            response["HX-Retarget"] = "#signup-error"
            return response
            
        # Send SMS OTP
        send_otp_sms(phone_number)
        
        return render(request, "authentication/verify_code_signup.html", {"phone_number": phone_number})
        
    return render(request, "authentication/signup.html", {"phone_init": phone_init})

def signup_verify_view(request):
    if request.method == "POST":
        phone_number = clean_phone_number(request.POST.get("phone_number", ""))
        otp = request.POST.get("otp", "").strip()
        
        if not phone_number or not otp:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Required fields missing.</div>')
            
        if verify_otp_sms(phone_number, otp):
            # Create user on successful OTP signup
            user, created = User.objects.get_or_create(phone_number=phone_number)
            login(request, user)
            
            # Redirect to reserve handle setup page
            response = HttpResponse()
            response["HX-Redirect"] = "/dashboard/setup/"
            return response
        else:
            return HttpResponse('<div class="text-red-400 text-xs mt-2">Incorrect verification code. Please check console logs.</div>')
            
    return redirect("authentication:signup")

from django.views.decorators.http import require_POST

@require_POST
def logout_view(request):
    logout(request)
    response = redirect("authentication:login")
    return response
