from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0005_widen_lieu_code_for_postgres_import"),
    ]

    operations = [
        # Lien ManyToMany formateur ↔ prestations
        migrations.AddField(
            model_name="prestation",
            name="ville",
            field=models.CharField(
                blank=True,
                default="",
                max_length=120,
                verbose_name="Ville de la prestation",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="formateur",
            name="prestations",
            field=models.ManyToManyField(
                blank=True,
                related_name="formateurs_assignes",
                to="formations.prestation",
                verbose_name="Prestations associées",
            ),
        ),
    ]
