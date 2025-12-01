
from django.db import models
from django.utils import timezone
from messages_core.models import Message
from messages_core.models import Session

class InjectResult(models.Model):
    id = models.BigAutoField(primary_key=True)
    message = models.ForeignKey(
        Message,
        to_field="id",
        db_column="message_uuid",
        on_delete=models.CASCADE,
        related_name="inject_results"
    )
    is_injection = models.BooleanField(default=False)
    injection_score = models.FloatField(null=True, blank=True)
    details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"InjectResult #{self.id} for Message {self.message_id}"


class AIResult(models.Model):

    id = models.BigAutoField(primary_key=True)

    # Link to the original message
    session = models.ForeignKey(
        Session,
        to_field="session_uuid",
        db_column="session_uuid",
        on_delete=models.CASCADE,
        related_name="ai_results"
    )
    message = models.ForeignKey(
        Message,
        to_field="message_uuid",
        db_column="message_uuid",
        on_delete=models.CASCADE,
        related_name="ai_results"
    )

    # Optional: store prompt & raw AI output for debugging + evaluation
    prompt = models.JSONField(blank=True, null=True)
    message_type = models.CharField(max_length=64, blank=True, null=True)  # e.g., inquiry, complaint


    # ---- CORE FLAGS ----
    is_injection = models.BooleanField(default=False)

    # ---- SCORES ----
    routing_confidence = models.FloatField(null=True, blank=True)  #0.0 -0.1

    # ---- ROUTING ----
    suggested_department_name = models.CharField(max_length=255, null=True, blank=True)  # AI predicted
    suggested_department_id = models.UUIDField(null=True, blank=True)

    corrected_by_operator = models.BooleanField(default=False)  # Auto-route overridden
    operator_uuid = models.UUIDField(null=True, blank=True)
    operator_corrected_department_id = models.IntegerField(null=True, blank=True)
    operator_corrected_department_name = models.CharField(max_length=255, null=True, blank=True)
    explanation = models.TextField(blank=True, null=True)

    # ---- VECTOR DB DEBUG INFO ----
    vector_similarity_score = models.FloatField(null=True, blank=True)  # similarity distance
    vector_top_candidates = models.JSONField(blank=True, null=True)  # e.g., [{"dept": "...", "score": 0.88}, ...]

    message_raw_embedding = models.JSONField(blank=True, null=True)  # optional: store embedding (if small)

    # ---- REASONING ---
    reason = models.TextField(blank=True, null=True) # optional explanation / debug info
    nlp_metadata = models.JSONField(blank=True, null=True)  # keywords, intents, entities, etc.

    # ---- Performance ----
    ai_processed_at = models.DateTimeField(default=timezone.now)
    process_duration_ms = models.IntegerField(null=True, blank=True)

    # ---- Timestamps ----
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Result"
        verbose_name_plural = "AI Results"
        indexes = [
            models.Index(fields=["message"]),
            models.Index(fields=["suggested_department_id"]),
            models.Index(fields=["operator_uuid"]),
            models.Index(fields=["operator_corrected_department_id"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["updated_at"]),
        ]

    def __str__(self):
        return f"AIResult #{self.id} for Message {self.message_id}"
