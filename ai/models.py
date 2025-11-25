
from django.db import models
from django.utils import timezone
from user_messages.models import Message


class AIResult(models.Model):

    id = models.BigAutoField(primary_key=True)

    # Link to the original message
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="ai_results"
    )

    # Optional: store prompt & raw AI output for debugging + evaluation
    prompt = models.TextField(blank=True, null=True)
    ai_response = models.JSONField(blank=True, null=True)
    message_type = models.CharField(max_length=64, blank=True, null=True)  # e.g., inquiry, complaint


    # ---- CORE FLAGS ----
    is_injection = models.BooleanField(default=False)  
    is_ai_auto_answer = models.BooleanField(default=False)

    # ---- SCORES ----
    complexity_score = models.FloatField(null=True, blank=True)  # 0–10
    routing_confidence = models.FloatField(null=True, blank=True)  # 0–10
    answer_confidence = models.FloatField(null=True, blank=True)  # 0–10

    # ---- ROUTING ----
    suggested_department_uuid_by_ai = models.UUIDField(null=True, blank=True)  # AI predicted
    final_department_uuid = models.UUIDField(null=True, blank=True)  # After human validation or fallback

    forced_by_operator = models.BooleanField(default=False)  # Auto-route overridden
    operator_corrected_department_uuid = models.UUIDField(null=True, blank=True)
    explanation = models.TextField(blank=True, null=True)
    operator_uuid = models.UUIDField(null=True, blank=True)

    # ---- VECTOR DB DEBUG INFO ----
    vector_similarity_score = models.FloatField(null=True, blank=True)  # similarity distance
    vector_top_candidates = models.JSONField(blank=True, null=True)  # e.g., [{"dept": "...", "score": 0.88}, ...]

    raw_embedding = models.JSONField(blank=True, null=True)  # optional: store embedding (if small)

    # ---- REASONING ----
    decision = models.CharField(max_length=255, blank=True, null=True)  # e.g., "route to billing dept"
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
            models.Index(fields=["suggested_department_uuid_by_ai"]),
            models.Index(fields=["final_department_uuid"]),
        ]

    def __str__(self):
        return f"AIResult #{self.id} for Message {self.message_id}"
