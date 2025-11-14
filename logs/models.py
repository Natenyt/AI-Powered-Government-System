import uuid
import hashlib
from datetime import datetime
from django.db import models, transaction
from django.utils import timezone


class AuditLog(models.Model):
    """
    Ultra-Enterprise Audit Log with tamper-detection via chained SHA256 hashes.
    Append-only design; do not update records once created (logical enforcement).
    """

    # Primary identification
    id = models.BigAutoField(primary_key=True)
    log_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    # Actor
    ACTOR_TYPE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
        ('superadmin', 'SuperAdmin'),
        ('system', 'System'),
        ('service', 'Service'),
        ('ai', 'AI'),
    ]
    actor_type = models.CharField(max_length=16, choices=ACTOR_TYPE_CHOICES, db_index=True)
    actor_uuid = models.UUIDField(blank=True, null=True, db_index=True, editable=False)
    actor_metadata = models.JSONField(blank=True, null=True)

    # Organizational context
    organization_code = models.CharField(max_length=64, blank=True, null=True)
    department_id = models.IntegerField(blank=True, null=True)

    # Target object (recommended)
    object_type = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    object_uuid = models.UUIDField(blank=True, null=True, db_index=True)

    # Event details
    module = models.CharField(max_length=128, db_index=True)
    action = models.CharField(max_length=128, db_index=True)
    event_metadata = models.JSONField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    # Request / source info
    source_type = models.CharField(max_length=32, blank=True, null=True)
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    geo_info = models.JSONField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True, null=True)
    request_id = models.UUIDField(blank=True, null=True)
    correlation_id = models.UUIDField(blank=True, null=True)
    session_id = models.UUIDField(blank=True, null=True)

    # Tamper-proof chain fields
    previous_hash = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    entry_hash = models.CharField(max_length=128, editable=False, db_index=True)
    signature = models.TextField(blank=True, null=True)
    signer_info = models.JSONField(blank=True, null=True)

    # Policy violations
    policy_violation = models.BooleanField(default=False, editable=False)
    severity = models.CharField(
        max_length=16,
        choices=[
            ('info','Info'),
            ('low','Low'),
            ('medium','Medium'),
            ('high','High'),
            ('critical','Critical')
        ],
        default='info'
    )

    # Soft-deletion
    immutable = models.BooleanField(default=True, editable=False)
    is_deleted = models.BooleanField(default=False, editable=False)
    deleted_at = models.DateTimeField(blank=True, null=True, editable=False)
    delete_reason = models.TextField(blank=True, null=True)
    delete_requested_by = models.UUIDField(blank=True, null=True, editable=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


    # ------------------------------------------------------
    # Helper functions start here
    # ------------------------------------------------------

    @staticmethod
    def compute_hash(data: dict) -> str:
        """
        Compute a SHA256 hash based on a dictionary.
        Keys are sorted to ensure consistent hashing.
        """
        payload = ""
        for key in sorted(data.keys()):
            payload += f"{key}:{data[key]};"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


    @classmethod
    def get_last_log(cls):
        """Returns the most recently created log entry."""
        return cls.objects.order_by("-id").first()


    @classmethod
    def create_log(
        cls,
        actor_type: str,
        module: str,
        action: str,
        actor_uuid=None,
        description=None,
        event_metadata=None,
        object_type=None,
        object_uuid=None,
        organization_code=None,
        department_id=None,
        source_type=None,
        ip_address=None,
        geo_info=None,
        user_agent=None,
        status=None,
        policy_violation=False,
        severity="info",
        request_id=None,
        correlation_id=None,
        session_id=None,
        signature=None,
        signer_info=None,
    ):
        """
        Creates a new audit log entry with hash chaining.
        Designed to be tamper-evident and append-only.
        """

        with transaction.atomic():
            previous = cls.get_last_log()
            previous_hash = previous.entry_hash if previous else None

            # Payload used for hashing
            data_for_hash = {
                "actor_type": actor_type,
                "actor_uuid": actor_uuid,
                "module": module,
                "action": action,
                "description": description or "",
                "object_type": object_type or "",
                "object_uuid": str(object_uuid) if object_uuid else "",
                "previous_hash": previous_hash or "",
                "timestamp": str(timezone.now()),
            }

            entry_hash = cls.compute_hash(data_for_hash)

            log = cls.objects.create(
                actor_type=actor_type,
                actor_uuid=actor_uuid,
                module=module,
                action=action,
                description=description,
                event_metadata=event_metadata,
                object_type=object_type,
                object_uuid=object_uuid,
                organization_code=organization_code,
                department_id=department_id,
                source_type=source_type,
                ip_address=ip_address,
                geo_info=geo_info,
                user_agent=user_agent,
                status=status,
                policy_violation=policy_violation,
                severity=severity,
                request_id=request_id,
                correlation_id=correlation_id,
                session_id=session_id,
                previous_hash=previous_hash,
                entry_hash=entry_hash,
                signature=signature,
                signer_info=signer_info,
            )

            return log


    def soft_delete(self, requested_by_uuid: uuid.UUID, reason: str = None):
        """
        Soft deletes a log entry.
        The log remains preserved but hidden from standard queries.
        """

        if not requested_by_uuid:
            raise ValueError("requested_by_uuid is required for soft deletion.")

        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.delete_reason = reason
        self.delete_requested_by = requested_by_uuid
        self.save(update_fields=["is_deleted", "deleted_at", "delete_reason", "delete_requested_by"])


    @classmethod
    def restore_deleted(cls, log_uuid: uuid.UUID):
        """
        Restores a soft-deleted log entry.
        """

        entry = cls.objects.filter(log_uuid=log_uuid, is_deleted=True).first()
        if entry:
            entry.is_deleted = False
            entry.deleted_at = None
            entry.delete_reason = None
            entry.delete_requested_by = None
            entry.save(update_fields=["is_deleted", "deleted_at", "delete_reason", "delete_requested_by"])
        return entry


    @classmethod
    def verify_chain(cls):
        """
        Verifies the entire hash chain. Returns a list of issues if found.
        """
        issues = []
        logs = cls.objects.order_by("id")

        previous_hash = None
        for log in logs:
            data = {
                "actor_type": log.actor_type,
                "actor_uuid": str(log.actor_uuid) if log.actor_uuid else "",
                "module": log.module,
                "action": log.action,
                "description": log.description or "",
                "object_type": log.object_type or "",
                "object_uuid": str(log.object_uuid) if log.object_uuid else "",
                "previous_hash": previous_hash or "",
                "timestamp": str(log.created_at),
            }

            computed = cls.compute_hash(data)

            if computed != log.entry_hash:
                issues.append(f"Hash mismatch at log ID {log.id}")

            if log.previous_hash != previous_hash:
                issues.append(f"Chain break at log ID {log.id}")

            previous_hash = log.entry_hash

        return issues



class ErrorLog(models.Model):
    """
    Enterprise-grade error logging model for tracking system and user-related errors.
    """

    # Primary identification
    id = models.BigAutoField(primary_key=True)
    error_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    # Error context
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    error_severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default='info')
    module = models.CharField(max_length=128, db_index=True)
    error_code = models.CharField(max_length=64, blank=True, null=True)
    error_message = models.TextField()
    stack_trace = models.TextField(blank=True, null=True)
    additional_metadata = models.JSONField(blank=True, null=True)

    # Request / user info
    involved_person_uuid = models.UUIDField(blank=True, null=True, db_index=True)
    request_id = models.UUIDField(blank=True, null=True)
    session_id = models.UUIDField(blank=True, null=True)
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    geo_info = models.JSONField(blank=True, null=True)

    # Linked audit log
    linked_audit_log_uuid = models.UUIDField(blank=True, null=True, db_index=True)

    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
    ]
    error_status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='pending')
    resolved_by = models.JSONField(blank=True, null=True)  # e.g., { "uuid": "...", "name": "...", "role": "developer" }
    resolved_at = models.DateTimeField(blank=True, null=True)

    # Timestamps
    error_time = models.DateTimeField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Error Log"
        verbose_name_plural = "Error Logs"
        indexes = [
            models.Index(fields=["error_uuid"]),
            models.Index(fields=["module"]),
            models.Index(fields=["involved_person_uuid"]),
            models.Index(fields=["error_status"]),
            models.Index(fields=["linked_audit_log_uuid"]),
        ]

    def __str__(self):
        return f"Error [{self.error_severity}] in {self.module} at {self.error_time}"

    def mark_resolved(self, resolver_info: dict):
        """
        Marks this error as resolved.
        resolver_info: dict containing developer/worker info, e.g., { "uuid": "...", "name": "..."}
        """
        self.error_status = 'resolved'
        self.resolved_by = resolver_info
        self.resolved_at = timezone.now()
        self.save()

    @classmethod
    def create_error_log(
        cls,
        module: str,
        error_message: str,
        severity: str = 'info',
        involved_person_uuid: uuid.UUID = None,
        request_id: uuid.UUID = None,
        session_id: uuid.UUID = None,
        ip_address: str = None,
        geo_info: dict = None,
        stack_trace: str = None,
        error_code: str = None,
        additional_metadata: dict = None
    ) -> "ErrorLog":
        """
        Creates a new ErrorLog entry and automatically links it to the most recent relevant AuditLog.
        """
        # Create the error log object
        error_log = cls.objects.create(
            module=module,
            error_message=error_message,
            error_severity=severity,
            involved_person_uuid=involved_person_uuid,
            request_id=request_id,
            session_id=session_id,
            ip_address=ip_address,
            geo_info=geo_info,
            stack_trace=stack_trace,
            error_code=error_code,
            additional_metadata=additional_metadata
        )

        # Attempt to link the most recent relevant audit log
        try:
            audit_log = AuditLog.objects.filter(
                module=module,
                actor_uuid=involved_person_uuid,
                request_id=request_id,
                session_id=session_id
            ).order_by('-created_at').first()

            if audit_log:
                error_log.linked_audit_log_uuid = audit_log.log_uuid
                error_log.save()
        except AuditLog.DoesNotExist:
            pass

        return error_log
