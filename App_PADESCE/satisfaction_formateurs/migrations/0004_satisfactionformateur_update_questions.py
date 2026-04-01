from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("satisfaction_formateurs", "0003_satisfactionformateur_transcription"),
    ]

    operations = [
        # --- Ajout des nouveaux champs ---
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q1_prerequis_apprenants",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q2_interaction_apprenants",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q3_competences_acquises",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q4_gestion_administrative",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q5_gestion_financiere",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="satisfactionformateur",
            name="q6_communication",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
        # --- Suppression des anciens champs ---
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q1_motivation_apprenants",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q2_niveau_prerequis",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q3",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q4",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q5",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q6",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q7",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q8",
        ),
        migrations.RemoveField(
            model_name="satisfactionformateur",
            name="q9_satisfaction_globale_prestataire",
        ),
    ]
