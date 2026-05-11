from django.conf import settings
from django.db import models
from django.utils import timezone

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Inspecteur


class PresenceControl(TimeStampedModel):
    CONFORMITE_CHOICES = [
        ("conforme", "Conforme"),
        ("non_conforme", "Non Conforme"),
    ]
    TYPE_CONTROLE_CHOICES = [(f"C{i}", f"C{i}") for i in range(1, 7)]

    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="presence_controls")
    inspecteur = models.ForeignKey(
        Inspecteur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presence_controls",
    )
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presence_controls_saisis",
    )
    theme = models.CharField("Thème de la séance", max_length=255)
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    conformite = models.CharField(
        "Conformité", max_length=20, choices=CONFORMITE_CHOICES, blank=True
    )
    type_controle = models.CharField(max_length=2, choices=TYPE_CONTROLE_CHOICES)
    duree_prevue_formation = models.DecimalField(
        "Durée prévue de la formation", max_digits=8, decimal_places=2, null=True, blank=True
    )
    formateur1_nom = models.CharField("Nom du formateur 1", max_length=255, blank=True)
    formateur1_telephone = models.CharField("Téléphone formateur 1", max_length=30, blank=True)
    formateur2_nom = models.CharField("Nom du formateur 2", max_length=255, blank=True)
    formateur2_telephone = models.CharField("Téléphone formateur 2", max_length=30, blank=True)
    formateur3_nom = models.CharField("Nom du formateur 3", max_length=255, blank=True)
    formateur3_telephone = models.CharField("Téléphone formateur 3", max_length=30, blank=True)
    teams_sent_at = models.DateTimeField(null=True, blank=True)
    teams_file_url = models.URLField(max_length=1000, blank=True)
    teams_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "classe__code", "type_controle"]
        constraints = [
            models.UniqueConstraint(
                fields=["classe", "type_controle"],
                name="presence_control_unique_type_par_classe",
            )
        ]
        indexes = [models.Index(fields=["classe", "type_controle"])]

    @property
    def jour(self) -> str:
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        if not self.date:
            return ""
        return jours[self.date.weekday()]

    def mark_teams_sent(self, file_url: str, message: str = "") -> None:
        self.teams_sent_at = timezone.now()
        self.teams_file_url = file_url or ""
        self.teams_message = message or ""
        self.save(update_fields=["teams_sent_at", "teams_file_url", "teams_message", "updated_at"])

    def __str__(self) -> str:
        return f"{self.classe.code} - {self.type_controle} - {self.date}"


class Presence(TimeStampedModel):
    PRESENCE_CHOICES = [("PR", "Présent"), ("AB", "Absent")]
    STATUT_CHOICES = [("present", "Présent"), ("absent", "Absent")]
    MOYEN_CHOICES = [("", "Non renseigné"), ("C", "Code"), ("P", "Papier"), ("R", "Rien")]

    controle = models.ForeignKey(
        PresenceControl,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="presences",
    )
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="presences")
    apprenant = models.ForeignKey(Apprenant, on_delete=models.CASCADE, related_name="presences")
    inspecteur = models.ForeignKey(
        Inspecteur, on_delete=models.SET_NULL, null=True, blank=True, related_name="presences"
    )
    enqueteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presences_saisies",
    )
    date = models.DateField()
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)
    presence = models.CharField(max_length=2, choices=PRESENCE_CHOICES, default="AB")
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default="absent")
    moyen_enregistrement = models.CharField(
        max_length=1, choices=MOYEN_CHOICES, default="", blank=True
    )
    remarques = models.TextField(blank=True)
    heure_presence = models.TimeField(null=True, blank=True)
    heure_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "classe"]
        constraints = [
            models.UniqueConstraint(
                fields=["controle", "apprenant"], name="presence_unique_par_controle"
            )
        ]
        indexes = [models.Index(fields=["classe", "date"]), models.Index(fields=["controle"])]

    def __str__(self) -> str:
        return f"{self.classe} - {self.apprenant} - {self.date}"
