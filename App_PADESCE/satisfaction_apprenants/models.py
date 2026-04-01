from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Inspecteur

NOTE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class SatisfactionApprenant(TimeStampedModel):
    appel = models.OneToOneField(
        "appels.Appel",
        on_delete=models.SET_NULL,
        related_name="satisfaction_apprenant",
        null=True,
        blank=True,
    )
    classe = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        related_name="satisfactions_apprenants",
        null=True,
        blank=True,
    )
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
    q3_maitrise_contenu = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q4_salle_adequate = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q5_materiel_disponible = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q6_organisation_temps = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
    q7_utilite_formation = models.PositiveSmallIntegerField(validators=NOTE_VALIDATORS)
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
        if self.apprenant:
            target = str(self.apprenant)
        elif self.appel:
            target = f"{self.appel.code or '-'} - {self.appel.nom or 'Appel'}"
        elif self.classe:
            target = str(self.classe)
        else:
            target = "Sans rattachement"
        return f"Satisfaction apprenant {target} - {self.date}"


class Transcription(TimeStampedModel):
    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="transcriptions"
    )
    appel = models.ForeignKey(
        "appels.Appel", on_delete=models.SET_NULL, null=True, blank=True, related_name="transcriptions"
    )
    audio_path = models.CharField(max_length=500, blank=True)
    transcript = models.TextField(blank=True)
    engine = models.CharField(max_length=120, blank=True)
    extracted_answers_json = models.JSONField(default=dict, blank=True)
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="transcriptions_saisies"
    )

    class Meta:
        ordering = ["-created_at"]
        db_table = "transcriptions"
        indexes = [models.Index(fields=["created_at"]), models.Index(fields=["apprenant"])]

    def __str__(self) -> str:
        return f"Transcription {self.apprenant or self.appel or '-'}"
