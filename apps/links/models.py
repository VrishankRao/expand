from django.db import models
from django.core.exceptions import ValidationError
from apps.profiles.models import Profile

class Link(models.Model):
    SURFACE_TYPES = [
        ("group", "Group"),
        ("community", "Community"),
        ("channel", "Channel"),
        ("chat", "Chat"),
        ("business", "Business"),
        ("other", "Other"),
    ]
    
    DEFAULT_CTA_MAPPINGS = {
        "group": "Join our WhatsApp Group",
        "community": "Join our WhatsApp Community",
        "channel": "Follow our WhatsApp Channel",
        "chat": "Message us on WhatsApp",
        "business": "View our Catalog",
        "other": "Visit link",
    }

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="links"
    )
    
    url = models.URLField(max_length=2048)
    label = models.CharField(max_length=100)
    
    surface_type = models.CharField(
        max_length=20,
        choices=SURFACE_TYPES,
        default="other"
    )
    
    cta_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom CTA message on the action button"
    )
    
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        indexes = [
            models.Index(fields=["profile", "is_active", "sort_order"]),
        ]

    def clean(self):
        super().clean()
        
        # Resolve surface type dynamically if not set yet or is 'other'
        if self.url and (not self.surface_type or self.surface_type == "other"):
            from apps.profiles.utils import detect_whatsapp_link_type
            detected = detect_whatsapp_link_type(self.url)
            if detected != "other":
                if not self.profile.is_premium:
                    self.surface_type = detected

        # Enforce WhatsApp links only (unless upgraded to premium)
        if self.url:
            from apps.profiles.utils import detect_whatsapp_link_type
            is_whatsapp = detect_whatsapp_link_type(self.url) != "other"
            if not self.profile.is_premium and not is_whatsapp:
                raise ValidationError("Only WhatsApp links are allowed on XPAND.")
            
            if not is_whatsapp and self.surface_type != "other":
                raise ValidationError("Non-WhatsApp links can only be of type 'Other'.")
                
            if is_whatsapp and self.surface_type == "other":
                raise ValidationError("WhatsApp links cannot be of type 'Other'. Please select a valid WhatsApp category.")
                
            normalized_url = self.url.strip()
            if Link.objects.filter(profile=self.profile, url=normalized_url).exclude(pk=self.pk).exists():
                raise ValidationError("This link is already put up by the user.")
        
        # Enforce name and type uniqueness
        if self.label and self.surface_type:
            normalized_label = self.label.strip()
            if Link.objects.filter(
                profile=self.profile,
                label__iexact=normalized_label,
                surface_type=self.surface_type
            ).exclude(pk=self.pk).exists():
                raise ValidationError("A link with this name and group type already exists on your profile.")
        
        # Enforce link limit: 50 active links for premium, 10 for free-tier
        if self.is_active:
            active_count = Link.objects.filter(profile=self.profile, is_active=True).exclude(pk=self.pk).count()
            limit = 50 if self.profile.is_premium else 10
            if active_count >= limit:
                if self.profile.is_premium:
                    raise ValidationError("You have reached the limit of 50 active links.")
                else:
                    raise ValidationError("You have reached the limit of 10 active links on the free tier.")

    def save(self, *args, **kwargs):
        self.clean()
        from apps.profiles.utils import detect_whatsapp_link_type
        # Automatically detect surface type if not explicitly set or if set to default 'other'
        if not self.surface_type or self.surface_type == "other":
            detected = detect_whatsapp_link_type(self.url)
            if detected != "other" and not self.profile.is_premium:
                self.surface_type = detected
        
        # Populate default CTA if blank
        if not self.cta_text:
            self.cta_text = self.DEFAULT_CTA_MAPPINGS.get(self.surface_type, "Visit link")
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.label} ({self.get_surface_type_display()})"

    @property
    def favicon_url(self):
        from urllib.parse import urlparse
        import urllib.parse
        try:
            parsed = urlparse(self.url)
            domain = parsed.netloc or parsed.path
            if ":" in domain:
                domain = domain.split(":")[0]
            encoded_domain = urllib.parse.quote(domain)
            return f"https://www.google.com/s2/favicons?domain={encoded_domain}&sz=64"
        except Exception:
            try:
                encoded_url = urllib.parse.quote(self.url)
                return f"https://www.google.com/s2/favicons?domain={encoded_url}&sz=64"
            except Exception:
                return "https://www.google.com/s2/favicons?domain=example.com&sz=64"



class LinkClick(models.Model):
    link = models.ForeignKey(
        Link,
        on_delete=models.CASCADE,
        related_name="clicks"
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        db_index=True
    )
    visitor_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["link", "phone_number"]),
            models.Index(fields=["link", "ip_address"]),
            models.Index(fields=["link", "visitor_id"]),
        ]


    def __str__(self):
        return f"Click on {self.link.label} at {self.created_at}"

