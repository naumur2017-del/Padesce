from django.db import models

from App_PADESCE.core.models import TimeStampedModel


class Formateur(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    nom_complet = models.CharField(max_length=255)
    specialite = models.CharField(max_length=255, blank=True)
    qualification = models.CharField(max_length=255, blank=True)
    nb_annees_experience = models.PositiveIntegerField(default=0)
    fenetre = models.CharField(max_length=50, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    ville_residence = models.CharField(max_length=120, blank=True)
    autres_infos = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_complet"]

    def __str__(self) -> str:
        return f"{self.code} - {self.nom_complet}"


class Prestataire(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    raison_sociale = models.CharField(max_length=255)
    type_structure = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["raison_sociale"]

    def __str__(self) -> str:
        return f"{self.code} - {self.raison_sociale}"


class Formation(TimeStampedModel):
    STATUT_CHOICES = [
        ("non_demarre", "Non démarré"),
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
    ]

    code = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=255)
    nom_harmonise = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="non_demarre")
    fenetre = models.CharField(max_length=50, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return f"{self.code} - {self.nom}"


class Beneficiaire(TimeStampedModel):
    nom_structure = models.CharField(max_length=255)
    type_structure = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    departement = models.CharField(max_length=120, blank=True)
    arrondissement = models.CharField(max_length=120, blank=True)
    ville = models.CharField(max_length=120, blank=True)
    contact = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_structure"]
        verbose_name = "Bénéficiaire"
        verbose_name_plural = "Bénéficiaires"

    def __str__(self) -> str:
        return self.nom_structure


class Prestation(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    prestataire = models.ForeignKey(Prestataire, on_delete=models.CASCADE, related_name="prestations")
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="prestations")
    beneficiaire = models.ForeignKey(
        Beneficiaire, on_delete=models.SET_NULL, related_name="prestations", null=True, blank=True
    )
    effectif_a_former = models.PositiveIntegerField(default=0)
    femmes = models.PositiveIntegerField(default=0)
    cout_unitaire_psoaf = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_formation_psoaf_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cout_unitaire_mcdc_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_mcdc_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    duree_prevue_heures = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    duree_reelle_heures = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    jalons_contractuels = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.prestataire}"


class Lieu(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    nom_lieu = models.CharField(max_length=255)
    region = models.CharField(max_length=120, blank=True)
    departement = models.CharField(max_length=120, blank=True)
    arrondissement = models.CharField(max_length=120, blank=True)
    ville = models.CharField(max_length=120, blank=True)
    longitude = models.CharField(max_length=60, blank=True)
    latitude = models.CharField(max_length=60, blank=True)
    precision = models.CharField(max_length=255, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_lieu"]

    def __str__(self) -> str:
        return f"{self.code} - {self.nom_lieu}"


class Inspecteur(TimeStampedModel):
    code = models.CharField(max_length=20, unique=True)
    nom_complet = models.CharField(max_length=255)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom_complet"]

    def __str__(self) -> str:
        return f"{self.code} - {self.nom_complet}"


class Classe(TimeStampedModel):
    STATUT_CHOICES = [
        ("non_demarre", "Non démarré"),
        ("en_cours", "En cours"),
        ("termine", "Terminé"),
    ]

    code = models.CharField(max_length=20, unique=True)
    prestation = models.ForeignKey(Prestation, on_delete=models.CASCADE, related_name="classes")
    lieu = models.ForeignKey(Lieu, on_delete=models.SET_NULL, related_name="classes", null=True, blank=True)
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name="classes")
    intitule_formation = models.CharField(max_length=255)
    formateur = models.ForeignKey(Formateur, on_delete=models.SET_NULL, related_name="classes", null=True, blank=True)
    fenetre = models.CharField(max_length=50, blank=True)
    cohorte = models.PositiveIntegerField(default=1)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default="non_demarre")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["prestation", "fenetre"])]

    def __str__(self) -> str:
        return f"{self.code} - {self.intitule_formation}"
