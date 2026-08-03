from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("appels", "0034_appelpasforme_corrections"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name="AppelPasFormeII",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("reference_code", models.CharField(max_length=160, unique=True)), ("prestation_id", models.CharField(db_index=True, max_length=80)),
            ("nom", models.CharField(max_length=255)), ("telephone", models.CharField(blank=True, max_length=30)),
            ("beneficiaire", models.CharField(blank=True, max_length=255)), ("prestataire", models.CharField(blank=True, max_length=255)), ("genre", models.CharField(blank=True, max_length=20)),
            ("absent_dans_consolide", models.BooleanField(default=False)), ("total_presence", models.PositiveSmallIntegerField(blank=True, null=True)), ("total_seances", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("seuil_75", models.PositiveSmallIntegerField(blank=True, null=True)), ("nombre_seances_source", models.PositiveSmallIntegerField(blank=True, null=True)), ("forme_final", models.CharField(blank=True, max_length=80)),
            ("nombre_seances_declare", models.PositiveSmallIntegerField(blank=True, null=True)), ("is_active", models.BooleanField(db_index=True, default=True)),
            ("status", models.CharField(choices=[("en_attente", "En attente"), ("appel_tente", "Appel Tenté"), ("appel_reussi", "Appel Réussi"), ("formulaire_rempli", "Formulaire Rempli"), ("formulaire_avec_audio", "Formulaire avec Audio"), ("en_cours", "En cours"), ("pause", "Pause"), ("a_rappeler", "A rappeler"), ("termine", "Termine")], db_index=True, default="en_attente", max_length=25)),
            ("formulaire_rempli_at", models.DateTimeField(blank=True, null=True)), ("locked_at", models.DateTimeField(blank=True, null=True)),
            ("locked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appels_pas_forme_ii_lock", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["prestation_id", "nom"]},
    ), migrations.AddIndex(model_name="appelpasformeii", index=models.Index(fields=["prestation_id", "is_active", "status"], name="appels_appe_prestat_bfab74_idx"))]
