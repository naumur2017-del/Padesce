from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("created", "Created"),
        ("updated", "Updated"),
        ("deleted", "Deleted"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries"
    )
    model_name = models.CharField(max_length=200)
    object_pk = models.CharField(max_length=100)
    object_repr = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    extra = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["model_name"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self) -> str:
        actor = self.actor or "system"
        return f"{self.model_name} {self.object_pk} {self.action} by {actor}"


class UserActivity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity"
    )
    last_seen = models.DateTimeField()

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self) -> str:
        return f"{self.user} - {self.last_seen}"
