def theme_context(request):
    theme = "light"
    
    # Prioritize cookie preference to remember user choice across authenticated/anonymous sessions
    cookie_theme = request.COOKIES.get("theme_preference")
    if cookie_theme in ["light", "dark", "whatsapp-green"]:
        theme = cookie_theme
    elif request.user.is_authenticated:
        try:
            theme = request.user.profile.theme
        except Exception:
            pass
            
    return {"current_theme": theme}
