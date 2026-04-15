from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

import App_PADESCE.appels.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appels", "0009_appelanswers_appeltranscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppelFormateur",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reference_code", models.CharField(max_length=120, unique=True)),
                ("numero_seance", models.PositiveIntegerField(blank=True, null=True)),
                ("prestataire", models.CharField(blank=True, max_length=255)),
                ("beneficiaire", models.CharField(blank=True, max_length=255)),
                ("formation", models.CharField(blank=True, max_length=255)),
                ("lieu", models.CharField(blank=True, max_length=255)),
                ("telephone", models.CharField(blank=True, max_length=30)),
                ("cohorte", models.CharField(blank=True, max_length=100)),
                ("date_label", models.CharField(blank=True, max_length=120)),
                ("session_date", models.DateField(blank=True, null=True)),
                ("heure_debut", models.CharField(blank=True, max_length=30)),
                ("heure_fin", models.CharField(blank=True, max_length=30)),
                ("source_contact", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("en_cours", "En cours"),
                            ("pause", "Pause"),
                            ("a_rappeler", "A rappeler"),
                            ("termine", "Termine"),
                        ],
                        db_index=True,
                        default="en_attente",
                        max_length=20,
                    ),
                ),
                ("rappel_at", models.DateTimeField(blank=True, null=True)),
                (
                    "audio_file",
                    models.FileField(
                        blank=True,
                        max_length=255,
                        null=True,
                        upload_to=App_PADESCE.appels.models.appel_formateur_audio_upload,
                    ),
                ),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "locked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="appels_formateurs_lock",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["session_date", "numero_seance", "telephone"],
                "indexes": [
                    models.Index(fields=["prestataire"], name="appels_appe_prestat_1e4419_idx"),
                    models.Index(fields=["beneficiaire"], name="appels_appe_benefic_9716d2_idx"),
                    models.Index(fields=["formation"], name="appels_appe_formati_4738d7_idx"),
                    models.Index(fields=["cohorte"], name="appels_appe_cohorte_d0c21e_idx"),
                    models.Index(fields=["session_date"], name="appels_appe_session_06b286_idx"),
                    models.Index(fields=["telephone"], name="appels_appe_telepho_256921_idx"),
                ],
            },
        ),
    ]
