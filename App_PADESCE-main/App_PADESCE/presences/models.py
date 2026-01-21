from django.conf import settings
from django.db import models

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Inspecteur


class Presence(TimeStampedModel):
    PRESENCE_CHOICES = [("PR", "Présent"), ("AB", "Absent")]
    STATUT_CHOICES = [("present", "Présent"), ("absent", "Absent")]
    MOYEN_CHOICES = [("C", "Code"), ("P", "Papier")]

    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="presences")
    apprenant = models.ForeignKey(Apprenant, on_delete=models.CASCADE, related_name="presences")
    inspecteur = models.ForeignKey(Inspecteur, on_delete=models.SET_NULL, null=True, blank=True, related_name="presences")
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="presences_saisies"
    )
    date = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)
    presence = models.CharField(max_length=2, choices=PRESENCE_CHOICES, default="PR")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="present")
    moyen_enregistrement = models.CharField(max_length=1, choices=MOYEN_CHOICES, default="C")
    remarques = models.TextField(blank=True)
    heure_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "classe"]
        constraints = [
            models.UniqueConstraint(fields=["classe", "apprenant", "date"], name="presence_unique_par_jour")
        ]
        indexes = [models.Index(fields=["classe", "date"])]

    def __str__(self) -> str:
        return f"{self.classe} - {self.apprenant} - {self.date}"
