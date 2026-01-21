from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Inspecteur

NOTE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class SatisfactionApprenant(TimeStampedModel):
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="satisfactions_apprenants")
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="satisfactions"
    )
    inspecteur = models.ForeignKey(Inspecteur, on_delete=models.SET_NULL, null=True, blank=True)
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sat_appr_saisies"
    )
    date = models.DateField()
    heure = models.TimeField(null=True, blank=True)
    q1_clarte_exposes = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q2_interaction_formateur = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q3_rythme_formation = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q4_qualite_supports = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q5_applicabilite_contenu = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q6_organisation_logistique = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q7_respect_programme = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q8_adequation_besoins = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q9_satisfaction_globale = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    audio_appel = models.FileField(upload_to="enquetes/satisfaction_apprenants/", null=True, blank=True)
    transcription = models.TextField(blank=True)
    commentaire = models.TextField(blank=True)
    recommandations = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "classe"]
        indexes = [models.Index(fields=["classe"])]

    def __str__(self) -> str:
        return f"Satisfaction apprenant {self.classe} - {self.date}"
