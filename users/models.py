import uuid
from django.db import models

class SystemUser(models.Model):
    """
    Represents a unified user identity across all platforms (web, telegram, api, etc).
    """
    id = models.BigAutoField(primary_key=True)
    user_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    
    full_name = models.CharField(max_length=128, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True, unique=True)

    verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)
    
    # Meta data
    government_code = models.CharField(max_length=10, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    web_last_login = models.DateTimeField(blank=True, null=True)
    telegram_last_interaction = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "System User"
        verbose_name_plural = "System Users"
        indexes = [
            models.Index(fields=["user_uuid"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return self.full_name or f"User {self.user_uuid}"


class TelegramAccount(models.Model):
    """
    Represents a Telegram user linked to the SystemUser identity.
    """

    LANGUAGE_CHOICES = [
        ('uz', 'Uzbek'),
        ('ru', 'Russian'),
        ('en', 'English'),
    ]

    id = models.BigAutoField(primary_key=True)
    system_user = models.ForeignKey(
        SystemUser,
        on_delete=models.CASCADE,
        related_name="telegram_accounts"
    )

    telegram_chat_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=128, blank=True, null=True)
    full_name = models.CharField(max_length=128, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    is_bot = models.BooleanField(default=False)

    neighborhood = models.CharField(max_length=128, blank=True, null=True)
    language_code = models.CharField(max_length=8, blank=True, null=True)
    language_preference = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='uz'
    )
    location = models.CharField(max_length=256, blank=True, null=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    last_interaction = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Telegram {self.username or self.telegram_chat_id}"
    



class WebAccount(models.Model):
    """
    Represents a web platform user account linked to the SystemUser.
    Supports both local (password) and OAuth (Google) sign-ins.
    """
    id = models.BigAutoField(primary_key=True)
    system_user = models.ForeignKey(
        SystemUser,
        on_delete=models.CASCADE,
        related_name="web_accounts"
    )

    full_name = models.CharField(max_length=128, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=256, blank=True, null=True)
    neighborhood = models.CharField(max_length=128, blank=True, null=True)
    location = models.CharField(max_length=256, blank=True, null=True)


    # OAuth fields
    is_oauth = models.BooleanField(default=False)
    oauth_provider = models.CharField(max_length=32, blank=True, null=True)  # e.g., "google"
    oauth_sub = models.CharField(max_length=128, blank=True, null=True)  # Google "sub" claim (unique user ID)
    oauth_token = models.CharField(max_length=512, blank=True, null=True)  # Optional: store last access token
    oauth_avatar = models.URLField(blank=True, null=True)

    last_login = models.DateTimeField(blank=True, null=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.is_oauth:
            return f"{self.oauth_provider.title()} User ({self.email})"
        return f"Web {self.email}"

    class Meta:
        verbose_name = "Web Account"
        verbose_name_plural = "Web Accounts"