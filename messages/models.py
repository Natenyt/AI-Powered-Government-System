import uuid
from django.db import models
from django.utils import timezone
from departments.models import Department, SystemAdmin
from users.models import SystemUser


class Message(models.Model):
    """
    Represents a single message turnaround between a SystemUser and a SystemAdmin/AId.
    One row = one turnaround (user -> admin/AI -> user reply handled separately if needed).
    """

    # ---- Identification ----
    id = models.BigAutoField(primary_key=True)
    conversation_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    # ---- Sender info ----
    sender = models.ForeignKey(
        SystemUser,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )
    sender_platform = models.CharField(
        max_length=16,
        choices=[('web', 'Web'), ('telegram', 'Telegram')],
        default='web'
    )

    # ---- Receiver info ----
    RECEIVER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('ai', 'AI'),
    ]
    receiver_type = models.CharField(max_length=16, choices=RECEIVER_TYPE_CHOICES)
    receiver_admin = models.ForeignKey(
        SystemAdmin,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="received_messages"
    )
    receiver_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages"
    )

    # ---- Message content ----
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('file', 'File'),
        ('image', 'Image'),
    ]
    message_type = models.CharField(max_length=16, choices=MESSAGE_TYPE_CHOICES, default='text')
    message_content = models.TextField(blank=True, null=True)
    message_file_url = models.URLField(blank=True, null=True)

    # ---- Reply info ----
    replied = models.BooleanField(default=False)
    who_replied = models.ForeignKey(
        SystemAdmin,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="replied_messages"
    )
    reply_content = models.TextField(blank=True, null=True)
    reply_type = models.CharField(max_length=16, choices=MESSAGE_TYPE_CHOICES, blank=True, null=True)
    reply_file_url = models.URLField(blank=True, null=True)
    reply_platform = models.CharField(
        max_length=16,
        choices=[('web', 'Web'), ('telegram', 'Telegram'), ('ai', 'AI')],
        blank=True,
        null=True
    )
    reply_duration = models.DurationField(blank=True, null=True)  # time from message creation to reply

    # ---- Workflow / status ----
    STAGE_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('responded', 'Responded'),
        ('closed', 'Closed'),
        ('injection_detected', 'Injection Detected'),
    ]
    stage = models.CharField(max_length=32, choices=STAGE_CHOICES, default='pending')

    # ---- Timestamps ----

    created_at = models.DateTimeField(auto_now_add=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        indexes = [
            models.Index(fields=["conversation_id"]),
            models.Index(fields=["sender"]),
            models.Index(fields=["receiver_admin"]),
            models.Index(fields=["receiver_department"]),
        ]

    def __str__(self):
        return f"Message from {self.sender.full_name or self.sender.user_uuid} to {self.receiver_type} at {self.created_at}"

    def mark_replied(self, admin: SystemAdmin = None, content: str = '', platform: str = 'web', file_url: str = None):
        """
        Marks the message as replied.
        """
        self.replied = True
        self.who_replied = admin
        self.reply_content = content
        self.reply_platform = platform
        self.reply_file_url = file_url
        self.replied_at = timezone.now()
        self.reply_duration = self.replied_at - self.created_at
        self.stage = 'responded'
        self.save()
