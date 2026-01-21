from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("apprenants", "0003_optional_telephones"),
        ("formations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SmsLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("telephone", models.CharField(blank=True, max_length=30)),
                ("message", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("sent", "Envoye"), ("failed", "Echec")], max_length=10
                    ),
                ),
                ("detail", models.CharField(blank=True, max_length=255)),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                (
                    "apprenant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_logs",
                        to="apprenants.apprenant",
                    ),
                ),
                (
                    "classe",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sms_logs",
                        to="formations.classe",
                    ),
                ),
            ],
            options={
                "ordering": ["-sent_at"],
            },
        ),
        migrations.AddIndex(
            model_name="smslog",
            index=models.Index(fields=["status"], name="apprenants_status_9e3b67_idx"),
        ),
        migrations.AddIndex(
            model_name="smslog",
            index=models.Index(fields=["sent_at"], name="apprenants_sent_at_2b9f3c_idx"),
        ),
    ]
