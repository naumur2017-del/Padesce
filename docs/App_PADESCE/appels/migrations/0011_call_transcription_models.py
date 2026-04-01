from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0010_appelformateur"),
    ]

    operations = [
        migrations.AddField(
            model_name="appeltranscription",
            name="engine",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="appeltranscription",
            name="error_message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="appeltranscription",
            name="status",
            field=models.CharField(blank=True, default="pending", max_length=20),
        ),
        migrations.CreateModel(
            name="AppelCGATranscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transcription_text", models.TextField(blank=True)),
                ("status", models.CharField(blank=True, default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("engine", models.CharField(blank=True, max_length=120)),
                (
                    "appel_cga",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transcription",
                        to="appels.appelcga",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AppelFormateurTranscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("transcription_text", models.TextField(blank=True)),
                ("status", models.CharField(blank=True, default="pending", max_length=20)),
                ("error_message", models.TextField(blank=True)),
                ("engine", models.CharField(blank=True, max_length=120)),
                (
                    "appel_formateur",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transcription",
                        to="appels.appelformateur",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
