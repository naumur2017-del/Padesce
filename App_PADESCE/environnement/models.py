from django.conf import settings
from django.db import models

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Inspecteur


class EnqueteEnvironnement(TimeStampedModel):
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="enquetes_environnement")
    inspecteur = models.ForeignKey(Inspecteur, on_delete=models.SET_NULL, null=True, blank=True)
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="environnement_saisies"
    )
    date = models.DateField()
    heure_enregistrement = models.TimeField(null=True, blank=True)
    tables = models.BooleanField(default=False)
    chaises = models.BooleanField(default=False)
    ecran = models.BooleanField(default=False)
    videoprojecteur = models.BooleanField(default=False)
    ventilation = models.BooleanField(default=False)
    eclairage = models.BooleanField(default=False)
    aeration = models.BooleanField(default=False)
    prises_electriques = models.BooleanField(default=False)
    salle_propre = models.BooleanField(default=False)
    salle_accessible = models.BooleanField(default=False)
    salle_securisee = models.BooleanField(default=False)
    signaletique = models.BooleanField(default=False)
    commodite = models.BooleanField(default=False)
    accessibilite = models.BooleanField(default=False)
    securite = models.BooleanField(default=False)
    acces_eau = models.BooleanField(default=False)
    commentaire_salle = models.TextField(blank=True)
    commentaire_global = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "classe"]
        indexes = [models.Index(fields=["classe"])]

    def __str__(self) -> str:
        return f"Environnement {self.classe} - {self.date}"
