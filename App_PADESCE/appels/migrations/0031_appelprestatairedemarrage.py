import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import App_PADESCE.appels.models


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0013_seed_presence_inspecteurs"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appels", "0030_merge_0029_appelcga_source_0029_appelpasforme"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppelPrestataireDemarrage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reference_code", models.CharField(max_length=120, unique=True)),
                ("numero", models.PositiveIntegerField(blank=True, null=True)),
                ("prestataire_code", models.CharField(blank=True, db_index=True, max_length=80)),
                ("nom_prestataire", models.CharField(max_length=255)),
                ("nom_simplifie", models.CharField(blank=True, max_length=120)),
                ("telephone", models.CharField(blank=True, max_length=30)),
                ("match_method", models.CharField(blank=True, max_length=80)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("appel_tente", "Appel Tenté"),
                            ("appel_reussi", "Appel Réussi"),
                            ("formulaire_rempli", "Formulaire Rempli"),
                            ("formulaire_avec_audio", "Formulaire avec Audio"),
                            ("en_cours", "En cours"),
                            ("pause", "Pause"),
                            ("a_rappeler", "A rappeler"),
                            ("termine", "Termine"),
                        ],
                        db_index=True,
                        default="en_attente",
                        max_length=25,
                    ),
                ),
                ("rappel_at", models.DateTimeField(blank=True, null=True)),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "audio_file",
                    models.FileField(
                        blank=True,
                        max_length=255,
                        null=True,
                        upload_to=App_PADESCE.appels.models.appel_prestataire_demarrage_audio_upload,
                    ),
                ),
                (
                    "prestation_debutee",
                    models.CharField(
                        blank=True, choices=[("OUI", "Oui"), ("NON", "Non")], max_length=3
                    ),
                ),
                ("date_debut_prestation", models.DateField(blank=True, null=True)),
                (
                    "motif_non_demarrage",
                    models.CharField(
                        blank=True,
                        choices=[
                            (
                                "documents",
                                "Probleme de document (conventions, rapports, listes de beneficiaires, pieces requises)",
                            ),
                            ("autorisations", "Attente d'autorisations ou confirmation"),
                            ("logistique", "Probleme de logistique et lieux de formation"),
                            ("statut_prestataire", "Statut du prestataire dans le programme"),
                        ],
                        max_length=40,
                    ),
                ),
                ("commentaire", models.TextField(blank=True)),
                ("satisfaction_completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "locked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appels_prestataires_demarrage_lock",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "prestataire",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appels_demarrage",
                        to="formations.prestataire",
                    ),
                ),
            ],
            options={
                "ordering": ["nom_prestataire"],
                "indexes": [
                    models.Index(
                        fields=["prestataire_code"], name="appels_appe_prestat_605b36_idx"
                    ),
                    models.Index(fields=["nom_prestataire"], name="appels_appe_nom_pre_d7c6e7_idx"),
                    models.Index(fields=["telephone"], name="appels_appe_telepho_d9869d_idx"),
                    models.Index(
                        fields=["status", "is_active"], name="appels_appe_status_5f1aa2_idx"
                    ),
                ],
            },
        ),
    ]
