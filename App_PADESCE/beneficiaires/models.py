from django.db import models

from App_PADESCE.core.models import TimeStampedModel


class BeneficiaireUpload(TimeStampedModel):
    beneficiaire_nom = models.CharField(max_length=255)
    prestataire_nom = models.CharField(max_length=255)
    fichier = models.FileField(upload_to="beneficiaires/uploads/")
    est_rejete = models.BooleanField(default=False)
    erreurs = models.TextField(blank=True)
    erreurs_types = models.JSONField(default=list, blank=True)
    recap_stats = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        statut = "rejete" if self.est_rejete else "accepte"
        return f"{self.beneficiaire_nom} ({self.prestataire_nom}) - {statut}"
