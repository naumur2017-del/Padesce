from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Formateur, Inspecteur

NOTE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class SatisfactionFormateur(TimeStampedModel):
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="satisfactions_formateurs")
    formateur = models.ForeignKey(Formateur, on_delete=models.CASCADE, related_name="satisfactions")
    inspecteur = models.ForeignKey(Inspecteur, on_delete=models.SET_NULL, null=True, blank=True)
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sat_form_saisies"
    )
    date = models.DateField()
    heure = models.TimeField(null=True, blank=True)

    # Q1-Q3 : notation 1-5
    q1_prerequis_apprenants = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q2_interaction_apprenants = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q3_competences_acquises = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)

    # Q4-Q6 : questions ouvertes
    q4_gestion_administrative = models.TextField(blank=True)
    q5_gestion_financiere = models.TextField(blank=True)
    q6_communication = models.TextField(blank=True)

    audio_appel = models.FileField(upload_to="enquetes/satisfaction_formateurs/", null=True, blank=True)
    transcription = models.TextField(blank=True)
    commentaires = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "classe"]
        indexes = [models.Index(fields=["classe"])]

    def __str__(self) -> str:
        return f"Satisfaction formateur {self.classe} - {self.date}"
