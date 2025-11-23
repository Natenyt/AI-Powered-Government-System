import uuid
from django.db import models
from django.utils import timezone
from messages.models import Message


class AIResult(models.Model):
    """
    Stores AI analysis results for a specific message.
    Allows multiple AI predictions per message if needed.
    """

    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="ai_results"
    )
    prompt = models.TextField(blank=True, null=True)  # The prompt sent to the AI model
    ai_response = models.JSONField(blank=True, null=True)  # Raw AI model response

    # AI decision & metadata
    severity = models.CharField(max_length=32, blank=True, null=True)  # e.g., low, medium, high
    message_category = models.CharField(max_length=64, blank=True, null=True)  # e.g., inquiry, complaint
    message_content_category = models.CharField(max_length=64, blank=True, null=True)  # e.g., billing, technical
    ismessage_contain_injection = models.BooleanField(default=False) 
    decision = models.CharField(max_length=255)  # e.g., "route to billing dept"
    confidence = models.FloatField(null=True, blank=True)
    suggested_department = models.CharField(max_length=128, blank=True, null=True)
    reason = models.TextField(blank=True, null=True)  # optional explanation / debug info
    nlp_metadata = models.JSONField(blank=True, null=True)  # e.g., detected intent, keywords, embeddings
    isai_chooseto_answer = models.BooleanField(default=False)
    ai_processed_at = models.DateTimeField(default=timezone.now)
    process_duration_ms = models.IntegerField(null=True, blank=True)  # processing time in milliseconds
    # ----
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Result"
        verbose_name_plural = "AI Results"
        indexes = [
            models.Index(fields=["message"]),
        ]

    def __str__(self):
        return f"AIResult for Message {self.message.id} - {self.decision} ({self.confidence})"
