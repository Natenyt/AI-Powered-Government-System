import uuid
from django.db import models
from django.utils import timezone
from departments.models import Department, Admins
from users.models import Users


class Session(models.Model):
    id = models.BigAutoField(primary_key=True)
    session_uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    user = models.ForeignKey(
        Users,
        to_field="user_uuid",
        db_column="user_uuid",
        on_delete=models.CASCADE,
        related_name="sessions"
    )

    # Agent responding
    assigned_admin = models.ForeignKey(
        Admins,
        to_field="admin_uuid",
        db_column="assigned_admin_uuid",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    assigned_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    status = models.CharField(
        max_length=16,
        choices=[("open", "Open"), ("closed", "Closed")],
        default="open"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.session_uuid} ({self.user})"




class Message(models.Model):
    id = models.BigAutoField(primary_key=True)
    message_uuid = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    session = models.ForeignKey(
        Session,
        to_field="session_uuid",
        db_column="session_uuid",
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender_type = models.CharField(
        max_length=16,
        choices=[('user', 'User'), ('admin', 'Admin')],
        default='user'
    )

    sender_user = models.ForeignKey(
        Users,
        to_field="user_uuid",
        db_column="sender_user",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    sender_admin = models.ForeignKey(
        Admins,
        to_field="admin_uuid",
        db_column="sender_admin",
        on_delete=models.SET_NULL,
        null=True, blank=True
    )

    sender_platform = models.CharField(
        max_length=16,
        choices=[
            ('web', 'Web'),
            ('telegram', 'Telegram'),
        ],
        default='web'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Message {self.message_uuid}"



class MessageContent(models.Model):
    id = models.BigAutoField(primary_key=True)

    message = models.ForeignKey(
        Message,
        to_field="message_uuid",
        db_column="message_uuid",
        on_delete=models.CASCADE,
        related_name="contents"
    )

    # True content types
    content_type = models.CharField(
        max_length=32,
        choices=[
            ('text', 'Text'),
            ('image', 'Image'),
            ('video', 'Video'),
            ('file', 'File'),
            ('voice', 'Voice'),
            ('other', 'Other')
        ],
        default='text'
    )

    # TEXT
    text = models.TextField(null=True, blank=True)

    # WEB MEDIA
    file = models.FileField(upload_to="message_media/", null=True, blank=True)
    file_url = models.URLField(null=True, blank=True)

    # Telegram media
    file_token = models.CharField(max_length=128, null=True, blank=True)
    media_group_id = models.CharField(max_length=128, null=True, blank=True)

    # OPTIONAL CAPTION (used for media)
    caption = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Content {self.id} for Message {self.message_id}"
