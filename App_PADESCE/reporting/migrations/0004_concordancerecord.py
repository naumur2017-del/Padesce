from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reporting", "0003_widen_fields_for_postgres_import")]

    operations = [
        migrations.CreateModel(
            name="ConcordanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("genre", models.CharField(blank=True, max_length=50)),
                ("fenetre", models.CharField(blank=True, max_length=100)),
                ("payload", models.JSONField(default=dict)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["fenetre", "genre", "id"]},
        ),
        migrations.AddIndex(
            model_name="concordancerecord",
            index=models.Index(fields=["genre", "fenetre"], name="reporting_c_genre_4f84de_idx"),
        ),
    ]
