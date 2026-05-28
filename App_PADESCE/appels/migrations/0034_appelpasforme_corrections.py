from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0033_appelpasforme_connait_prestataire"),
    ]

    operations = [
        migrations.AddField(
            model_name="appelpasforme",
            name="beneficiaire_corrige",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="appelpasforme",
            name="prestataire_corrige",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
