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
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
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
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    last_latitude = models.FloatField(null=True, blank=True)
    last_longitude = models.FloatField(null=True, blank=True)
    last_city = models.CharField(max_length=100, blank=True, default="")
    last_country = models.CharField(max_length=100, blank=True, default="")
    current_page = models.CharField(max_length=255, blank=True, default="")
    current_page_title = models.CharField(max_length=255, blank=True, default="")
    last_action_type = models.CharField(max_length=30, blank=True, default="")
    last_action_label = models.CharField(max_length=255, blank=True, default="")
    last_action_target = models.CharField(max_length=255, blank=True, default="")
    last_action_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self) -> str:
        return f"{self.user} - {self.last_seen}"


class UserLoginLog(models.Model):
    """Historique des connexions : IP + géolocalisation par utilisateur."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_logs"
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["-logged_at"]
        indexes = [
            models.Index(fields=["user", "-logged_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.ip_address} ({self.logged_at})"


class UserActivityEvent(models.Model):
    EVENT_PAGE_VIEW = "page_view"
    EVENT_BUTTON_CLICK = "button_click"
    EVENT_LINK_CLICK = "link_click"
    EVENT_CHOICES = [
        (EVENT_PAGE_VIEW, "Page view"),
        (EVENT_BUTTON_CLICK, "Button click"),
        (EVENT_LINK_CLICK, "Link click"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_events"
    )
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    page_path = models.CharField(max_length=255, blank=True, default="")
    page_title = models.CharField(max_length=255, blank=True, default="")
    target_label = models.CharField(max_length=255, blank=True, default="")
    target_path = models.CharField(max_length=255, blank=True, default="")
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "-occurred_at"]),
            models.Index(fields=["event_type", "-occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.event_type} {self.page_path}"
