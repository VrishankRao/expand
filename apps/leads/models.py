from django.db import models
from django.core.validators import RegexValidator
from apps.links.models import Link

class Lead(models.Model):
    # E.164 WhatsApp lead phone validation
    phone_validator = RegexValidator(
        regex=r'^\+?[1-9]\d{1,14}$',
        message="WhatsApp number must be in the format: '+919999999999'. Up to 15 digits allowed."
    )

    # Maintain relation for active dashboards, set null if the link is deleted
    link = models.ForeignKey(
        Link,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )
    
    # Snapshot metadata to safeguard lead context
    link_url_snapshot = models.URLField(max_length=2048)
    link_label_snapshot = models.CharField(max_length=100)
    cta_text_snapshot = models.CharField(max_length=100)
    
    # Lead Captured Details
    name = models.CharField(max_length=100)
    email = models.EmailField()
    
    whatsapp_number = models.CharField(
        max_length=20,
        validators=[phone_validator]
    )
    message = models.TextField(blank=True)
    
    # Metadata for Spam Detection & Diagnostics
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["link", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        # Automatically snapshot link details if they exist on initial creation
        if not self.pk and self.link:
            self.link_url_snapshot = self.link.url
            self.link_label_snapshot = self.link.label
            self.cta_text_snapshot = self.link.cta_text
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Lead from {self.name} ({self.whatsapp_number})"
