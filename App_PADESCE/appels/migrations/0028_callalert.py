from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appels", "0027_import_audio_priority_answers"),
    ]

    operations = [
        migrations.CreateModel(
            name="CallAlert",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.CharField(
                        choices=[("padesce", "PADESCE"), ("cga", "CGA")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("alert_types", models.JSONField(blank=True, default=list)),
                ("details", models.TextField(blank=True)),
                ("page_path", models.CharField(blank=True, max_length=255)),
                ("page_title", models.CharField(blank=True, max_length=255)),
                ("call_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("call_label", models.CharField(blank=True, max_length=255)),
                ("call_status", models.CharField(blank=True, max_length=40)),
                ("last_actions", models.JSONField(blank=True, default=list)),
                ("user_agent", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("todo", "To Do"), ("doing", "Doing"), ("done", "Done")],
                        db_index=True,
                        default="todo",
                        max_length=20,
                    ),
                ),
                ("admin_seen_at", models.DateTimeField(blank=True, null=True)),
                ("first_response_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("reporter_seen_at", models.DateTimeField(blank=True, null=True)),
                ("admin_message", models.TextField(blank=True)),
                ("resolution_comment", models.TextField(blank=True)),
                (
                    "admin_seen_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="call_alerts_seen",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "assigned_to",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="call_alerts_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reporter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="call_alerts_reported",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "-created_at"],
                        name="callalert_status_created_idx",
                    ),
                    models.Index(
                        fields=["reporter", "-updated_at"],
                        name="callalert_reporter_updated_idx",
                    ),
                    models.Index(
                        fields=["source", "status"],
                        name="callalert_source_status_idx",
                    ),
                ],
            },
        ),
    ]
