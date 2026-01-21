from django.db import models

from App_PADESCE.core.models import TimeStampedModel
from App_PADESCE.formations.models import Classe, Formation


class Apprenant(TimeStampedModel):
    numero = models.CharField(max_length=20, blank=True)
    code = models.CharField(max_length=20, unique=True)
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="apprenants")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="apprenants")
    nom_complet = models.CharField(max_length=255)
    beneficiaire = models.CharField(max_length=255, blank=True)
    genre = models.CharField(max_length=20, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    fonction = models.CharField(max_length=255, blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    nb_annees_experience = models.PositiveIntegerField(default=0)
    fenetre = models.CharField(max_length=50, blank=True)
    prestataire = models.CharField(max_length=255, blank=True)
    intitule_formation_solicitee = models.CharField(max_length=255, blank=True)
    intitule_formation_dispensee = models.CharField(max_length=255, blank=True)
    ville_formation = models.CharField(max_length=255, blank=True)
    telephone1 = models.CharField(max_length=30, blank=True, null=True)
    telephone2 = models.CharField(max_length=30, blank=True, null=True)
    cohorte = models.CharField(max_length=50, blank=True)
    tel_formateur = models.CharField(max_length=30, blank=True)
    ville_residence = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    departement = models.CharField(max_length=120, blank=True)
    arrondissement = models.CharField(max_length=120, blank=True)
    lieu_formation = models.CharField(max_length=255, blank=True)
    precision_lieu = models.CharField(max_length=255, blank=True)
    longitude = models.CharField(max_length=50, blank=True)
    latitude = models.CharField(max_length=50, blank=True)
    code_ville = models.CharField(max_length=120, blank=True)
    appartenance_beneficiaire = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_complet"]
        constraints = [
            models.UniqueConstraint(fields=["classe", "nom_complet"], name="unique_nom_par_classe"),
            models.UniqueConstraint(fields=["formation", "telephone1"], name="unique_tel1_par_formation"),
        ]
        indexes = [models.Index(fields=["classe", "formation"])]

    def __str__(self) -> str:
        return f"{self.code} - {self.nom_complet}"


class SmsLog(TimeStampedModel):
    STATUS_CHOICES = [
        ("sent", "Envoye"),
        ("failed", "Echec"),
    ]

    apprenant = models.ForeignKey(
        Apprenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="sms_logs"
    )
    classe = models.ForeignKey(
        Classe, on_delete=models.SET_NULL, null=True, blank=True, related_name="sms_logs"
    )
    telephone = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    detail = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["sent_at"]),
        ]

    def __str__(self) -> str:
        target = self.apprenant or "inconnu"
        return f"SMS {self.status} - {target}"
