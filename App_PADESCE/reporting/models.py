from django.db import models


class ConsolidationRecord(models.Model):
    numero = models.CharField(max_length=20, blank=True)
    nom_complet = models.CharField(max_length=255, blank=True)
    beneficiaire = models.CharField(max_length=255, blank=True)
    genre = models.CharField(max_length=10, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    fonction = models.CharField(max_length=100, blank=True)
    qualification = models.CharField(max_length=100, blank=True)
    nb_annees_experience = models.PositiveIntegerField(null=True, blank=True)
    ville_residence = models.CharField(max_length=120, blank=True)
    prestataire = models.CharField(max_length=255, blank=True)
    intitule_formation_solicitee = models.CharField(max_length=255, blank=True)
    intitule_formation_dispensee = models.CharField(max_length=255, blank=True)
    fenetre = models.CharField(max_length=50, blank=True)
    ville_formation = models.CharField(max_length=120, blank=True)
    arrondissement = models.CharField(max_length=120, blank=True)
    departement = models.CharField(max_length=120, blank=True)
    region = models.CharField(max_length=120, blank=True)
    lieu_formation = models.CharField(max_length=255, blank=True)
    precision_lieu = models.CharField(max_length=255, blank=True)
    longitude = models.CharField(max_length=255, blank=True)
    latitude = models.CharField(max_length=255, blank=True)
    telephone1 = models.CharField(max_length=30, blank=True)
    telephone2 = models.CharField(max_length=30, blank=True)
    cohorte = models.CharField(max_length=50, blank=True)
    tel_formateur = models.CharField(max_length=255, blank=True)
    code = models.CharField(max_length=255, blank=True)
    cout_unitaire_subvention = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    montant_total_subvention = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    statut_prestation = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["numero", "nom_complet"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["nom_complet"]),
        ]

    def __str__(self) -> str:
        return f"{self.code or self.numero} - {self.nom_complet}"


class ConcordanceRecord(models.Model):
    """Ligne importée pour le suivi des travaux de concordance."""

    genre = models.CharField(max_length=50, blank=True)
    fenetre = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fenetre", "genre", "id"]
        indexes = [models.Index(fields=["genre", "fenetre"], name="reporting_c_genre_4f84de_idx")]


class PendingLearnerContactImport(models.Model):
    """Fichier courant des contacts à récupérer pour les prestations en attente."""

    source_filename = models.CharField(max_length=255, blank=True)
    headers = models.JSONField(default=list)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-imported_at", "-id"]


class PendingLearnerContactRecord(models.Model):
    """Ligne d'un fichier de contacts, conservée sans imposer son schéma source."""

    import_batch = models.ForeignKey(
        PendingLearnerContactImport,
        on_delete=models.CASCADE,
        related_name="records",
    )
    row_number = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)

    class Meta:
        ordering = ["row_number", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["import_batch", "row_number"],
                name="unique_pending_contact_row",
            )
        ]
