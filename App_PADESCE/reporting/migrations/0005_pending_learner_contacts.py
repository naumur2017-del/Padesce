import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reporting", "0004_concordancerecord")]

    operations = [
        migrations.CreateModel(
            name="PendingLearnerContactImport",
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
                ("source_filename", models.CharField(blank=True, max_length=255)),
                ("headers", models.JSONField(default=list)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-imported_at", "-id"]},
        ),
        migrations.CreateModel(
            name="PendingLearnerContactRecord",
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
                ("row_number", models.PositiveIntegerField()),
                ("payload", models.JSONField(default=dict)),
                (
                    "import_batch",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="reporting.pendinglearnercontactimport",
                    ),
                ),
            ],
            options={"ordering": ["row_number", "id"]},
        ),
        migrations.AddConstraint(
            model_name="pendinglearnercontactrecord",
            constraint=models.UniqueConstraint(
                fields=("import_batch", "row_number"),
                name="unique_pending_contact_row",
            ),
        ),
    ]
