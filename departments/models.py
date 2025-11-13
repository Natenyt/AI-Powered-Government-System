import uuid
from django.db import models

class Department(models.Model):
    """
    Represents a department within the system.
    """
    id = models.BigAutoField(primary_key=True)
    department_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    name = models.CharField(max_length=128, unique=True)
    code = models.CharField(max_length=16, unique=True, blank=True, null=True)  # optional short code
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=["department_uuid"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code or 'No Code'})"


import uuid
from django.db import models
from departments.models import Department  # assuming departments table exists

class SystemAdmin(models.Model):
    """
    Universal admin record referenced by platform-specific admin accounts.
    """
    id = models.BigAutoField(primary_key=True)
    admin_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    full_name = models.CharField(max_length=128)
    phone_number = models.CharField(max_length=32, blank=True, null=True, unique=True)

    # Optional link to a department
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="admins"
    )

    # Meta info
    role = models.CharField(max_length=64, default="operator")  # operator, department_head, super_admin, etc.
    permissions = models.JSONField(blank=True, null=True)  # optional granular permissions
    assigned_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_admins"
    )
    assigned_date = models.DateTimeField(blank=True, null=True)
    promoted_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="promoted_admins"
    )
    promoted_to = models.CharField(max_length=64, blank=True, null=True)
    promoted_date = models.DateTimeField(blank=True, null=True)

    web_last_login = models.DateTimeField(blank=True, null=True)
    last_telegram_interaction = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} ({self.role})"



class TelegramAdmin(models.Model):
    """
    Telegram-specific admin account linked to SystemAdmin.
    """
    id = models.BigAutoField(primary_key=True)
    system_admin = models.ForeignKey(
        SystemAdmin,
        on_delete=models.CASCADE,
        related_name="telegram_accounts"
    )
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    full_name = models.CharField(max_length=128, blank=True, null=True)
    telegram_chat_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=128, blank=True, null=True)
    language_code = models.CharField(max_length=8, blank=True, null=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    last_interaction = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Telegram Admin {self.username or self.telegram_chat_id}"



class WebAdmin(models.Model):
    """
    Web-specific admin account linked to SystemAdmin.
    """
    id = models.BigAutoField(primary_key=True)
    system_admin = models.ForeignKey(
        SystemAdmin,
        on_delete=models.CASCADE,
        related_name="web_accounts"
    )
    full_name = models.CharField(max_length=128, blank=True, null=True)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=256)
    last_login = models.DateTimeField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)

    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Web Admin {self.email}"