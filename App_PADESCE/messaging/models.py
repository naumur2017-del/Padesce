from django.conf import settings
from django.db import models

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Formation, Prestataire


class Contact(TimeStampedModel):
    apprenant = models.ForeignKey(
        "apprenants.Apprenant", on_delete=models.SET_NULL, null=True, blank=True, related_name="contacts"
    )
    nom_complet = models.CharField(max_length=255)
    telephone = models.CharField(max_length=30)
    genre = models.CharField(max_length=20, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    fonction = models.CharField(max_length=255, blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    nb_annees_experience = models.PositiveIntegerField(default=0)
    ville_residence = models.CharField(max_length=120, blank=True)
    prestataire = models.ForeignKey(Prestataire, on_delete=models.SET_NULL, null=True, blank=True)
    type_formation = models.CharField(max_length=255, blank=True)
    intitule_formation = models.CharField(max_length=255, blank=True)
    fenetre = models.CharField(max_length=50, blank=True)
    formation = models.ForeignKey(Formation, on_delete=models.SET_NULL, null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_complet"]
        indexes = [models.Index(fields=["prestataire", "fenetre"])]

    def __str__(self) -> str:
        return self.nom_complet


class CampagneMessage(TimeStampedModel):
    date_heure = models.DateTimeField()
    texte = models.TextField()
    cible_description = models.CharField(max_length=255, blank=True)
    message_envoye_json = models.JSONField(default=list, blank=True)
    message_rejete_json = models.JSONField(default=list, blank=True)
    motif_rejet = models.TextField(blank=True)
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="campagnes_saisies"
    )

    class Meta:
        ordering = ["-date_heure"]

    def __str__(self) -> str:
        return f"Campagne {self.date_heure}"
