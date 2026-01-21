from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("formations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Appel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=50, unique=True)),
                ("nom", models.CharField(max_length=255)),
                ("prestataire", models.CharField(blank=True, max_length=255)),
                ("beneficiaire", models.CharField(blank=True, max_length=255)),
                ("lieu", models.CharField(blank=True, max_length=255)),
                ("classe_label", models.CharField(blank=True, max_length=100)),
                ("telephone1", models.CharField(blank=True, max_length=30)),
                ("telephone2", models.CharField(blank=True, max_length=30)),
                ("taux_presence", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("status", models.CharField(choices=[("en_attente", "En attente"), ("en_cours", "En cours"), ("pause", "Pause"), ("a_rappeler", "A rappeler"), ("termine", "Termine")], default="en_attente", max_length=20)),
                ("rappel_at", models.DateTimeField(blank=True, null=True)),
                ("audio_file", models.FileField(blank=True, null=True, upload_to="appels/")),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("classe", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appels", to="formations.classe")),
                ("locked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="appels_lock", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["nom"],
            },
        ),
    ]
