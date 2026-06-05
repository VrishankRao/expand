from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator, FileExtensionValidator
from django.core.exceptions import ValidationError

# Strict handle validation: lowercase, alphanumeric, and underscores only
handle_validator = RegexValidator(
    regex=r'^[a-z0-9_]{3,30}$',
    message="Handle must be 3-30 characters long and contain only lowercase letters, numbers, and underscores."
)

RESERVED_HANDLES = {
    "admin", "login", "signup", "dashboard", "logout", "api", "static", "media", 
    "xpand", "help", "support", "privacy", "terms", "settings", "profile", "lead"
}

def validate_reserved_handle(value):
    if value.lower() in RESERVED_HANDLES:
        raise ValidationError(f"The handle '{value}' is reserved and cannot be used.")

class Profile(models.Model):
    THEME_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
        ("whatsapp-green", "WhatsApp Green"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    
    handle = models.CharField(
        max_length=30,
        unique=True,
        validators=[handle_validator, validate_reserved_handle],
        db_index=True,
        help_text="Custom URL handle at xpand.so/<handle>"
    )
    
    display_name = models.CharField(max_length=60)
    bio = models.TextField(max_length=200, blank=True)
    
    avatar = models.FileField(
        upload_to="avatars/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])]
    )
    
    # Toggle visibility (forced private until at least 1 active link is added)
    is_visible = models.BooleanField(default=False)
    
    # Email verification flow for Lead Notifications via AWS SES
    verified_email = models.EmailField(blank=True, null=True, unique=True)
    email_verified = models.BooleanField(default=False)
    
    theme = models.CharField(
        max_length=20,
        choices=THEME_CHOICES,
        default="light"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.handle:
            self.handle = self.handle.lower()
            
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"@{self.handle} ({self.display_name})"
