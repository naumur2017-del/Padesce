from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apprenants", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="apprenant",
            name="appartenance_beneficiaire",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="arrondissement",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="departement",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="region",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
