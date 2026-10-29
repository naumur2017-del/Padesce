from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from App_PADESCE.core.media_access import secure_media_upload_path


class Enterprise(models.Model):
    CAMPAIGN_PME = "pme"
    CAMPAIGN_FUNDS = "fonds_amorcage"
    CAMPAIGN_CHOICES = [(CAMPAIGN_PME, "PME"), (CAMPAIGN_FUNDS, "Fonds d’amorçage")]
    campaign = models.CharField(
        max_length=30,
        choices=CAMPAIGN_CHOICES,
        default=CAMPAIGN_PME,
        db_index=True,
        editable=False,
    )
    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("en_cours", "En cours"),
        ("pause", "En pause"),
        ("appel_tente", "Appel tenté"),
        ("appel_reussi", "Appel réussi"),
        ("a_rappeler", "À rappeler"),
        ("injoignable", "Injoignable"),
        ("numero_errone", "Numéro erroné"),
        ("refus", "Refus"),
        ("formulaire_avec_audio", "Formulaire avec audio"),
    ]
    reference = models.CharField(max_length=100, unique=True)
    source_number = models.CharField(max_length=60, blank=True)
    name = models.CharField(max_length=255, db_index=True)
    phone = models.CharField(max_length=150, blank=True)
    phone_raw = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=150, blank=True, db_index=True)
    sector = models.CharField(max_length=180, blank=True, db_index=True)
    annual_revenue_fcfa = models.DecimalField(
        max_digits=20, decimal_places=0, null=True, blank=True
    )
    source_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="en_attente", db_index=True
    )
    callback_at = models.DateTimeField(null=True, blank=True, db_index=True)
    answers = models.JSONField(default=dict, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fa_enterprises",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        indexes = [models.Index(fields=["status", "name"], name="fa_enterprise_status_name")]

    def __str__(self):
        return self.name

    @property
    def phone_numbers(self):
        return [number.strip() for number in self.phone.split(" / ") if number.strip()]


class CallAttempt(models.Model):
    enterprise = models.ForeignKey(Enterprise, on_delete=models.PROTECT, related_name="attempts")
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="fa_call_attempts",
    )
    client_token = models.UUIDField(unique=True)
    status = models.CharField(max_length=30, choices=Enterprise.STATUS_CHOICES, default="en_cours")
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    callback_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    answers = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["enterprise"],
                condition=Q(ended_at__isnull=True),
                name="fa_one_open_attempt",
            )
        ]
        indexes = [models.Index(fields=["agent", "started_at"], name="fa_attempt_agent_date")]

    @property
    def duration_seconds(self):
        return max(0, int(((self.ended_at or timezone.now()) - self.started_at).total_seconds()))


def recording_upload_path(instance, filename):
    return secure_media_upload_path("fa/recordings", filename, default_ext="webm")


class Recording(models.Model):
    attempt = models.ForeignKey(CallAttempt, on_delete=models.PROTECT, related_name="recordings")
    sequence = models.PositiveIntegerField()
    audio_file = models.FileField(upload_to=recording_upload_path, max_length=255)
    is_final = models.BooleanField(default=False)
    content_type = models.CharField(max_length=100, default="audio/webm")
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["sequence", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["attempt", "sequence"], name="fa_recording_attempt_seq")
        ]
