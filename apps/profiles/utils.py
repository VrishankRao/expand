from urllib.parse import urlparse

def detect_whatsapp_link_type(url: str) -> str:
    """
    Parses a WhatsApp URL and classifies it into:
    'group', 'community', 'channel', 'chat', 'business', or 'other'.
    Supports internationalized locale paths and missing schemes.
    """
    if not url:
        return "other"
        
    url = url.strip()
    
    # Auto-prepend scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
        
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    
    # Strip www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
        
    # Validate WhatsApp domain/subdomain
    if domain != "wa.me" and not domain.endswith("whatsapp.com"):
        return "other"
        
    # 1. Channel links
    if "/channel/" in path:
        return "channel"
        
    # 2. Community links
    if "/community/" in path:
        return "community"
        
    # 3. Group links
    if "/invite/" in path or "/group/" in path or domain == "chat.whatsapp.com":
        return "group"
        
    # 4. Business messages or catalogs
    if "/p/" in path or "/message/" in path:
        return "business"
        
    # Default to direct chat link
    return "chat"

