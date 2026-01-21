from django.conf import settings
from django.db import models

from django.utils import timezone
from django.utils.text import slugify

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe


def appel_audio_upload(instance: "Appel", filename: str) -> str:
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    nom_slug = slugify(instance.nom) or "appel"
    code_slug = slugify(instance.code) or "code"
    ext = filename.split(".")[-1] if "." in filename else "mp3"
    return f"appels/{nom_slug}-{code_slug}-{ts}.{ext}"


class Appel(TimeStampedModel):
    STATUS_CHOICES = [
        ("en_attente", "En attente"),
        ("en_cours", "En cours"),
        ("pause", "Pause"),
        ("a_rappeler", "A rappeler"),
        ("termine", "Termine"),
    ]

    code = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=255)
    prestataire = models.CharField(max_length=255, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    lieu = models.CharField(max_length=255, blank=True)
    classe_label = models.CharField(max_length=100, blank=True)
    classe = models.ForeignKey(Classe, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels")
    telephone1 = models.CharField(max_length=30, blank=True)
    telephone2 = models.CharField(max_length=30, blank=True)
    taux_presence = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="en_attente")
    rappel_at = models.DateTimeField(null=True, blank=True)
    type_formation_declaree = models.CharField(max_length=255, blank=True)
    formation_padesce = models.CharField(max_length=255, blank=True)
    deja_forme = models.BooleanField(default=False)
    audio_file = models.FileField(upload_to=appel_audio_upload, null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels_lock"
    )
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return f"Appel {self.code} - {self.nom}"
