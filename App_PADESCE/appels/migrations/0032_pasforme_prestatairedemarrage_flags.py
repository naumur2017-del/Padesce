from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0031_appelprestatairedemarrage"),
    ]

    operations = [
        migrations.AddField(
            model_name="appelpasforme",
            name="bon_numero",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="appelpasforme",
            name="faux_nom",
            field=models.CharField(
                blank=True, choices=[("OUI", "Oui"), ("NON", "Non")], max_length=3
            ),
        ),
        migrations.AddField(
            model_name="appelpasforme",
            name="faux_numero",
            field=models.CharField(
                blank=True, choices=[("OUI", "Oui"), ("NON", "Non")], max_length=3
            ),
        ),
        migrations.AddField(
            model_name="appelpasforme",
            name="vrai_nom",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="appelprestatairedemarrage",
            name="bon_numero",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="appelprestatairedemarrage",
            name="faux_numero",
            field=models.CharField(
                blank=True, choices=[("OUI", "Oui"), ("NON", "Non")], max_length=3
            ),
        ),
    ]
