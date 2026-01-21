from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apprenants", "0005_rename_apprenants_status_9e3b67_idx_apprenants__status_9c1d64_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="apprenant",
            name="beneficiaire",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="cohorte",
            field=models.CharField(blank=True, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="intitule_formation_dispensee",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="intitule_formation_solicitee",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="latitude",
            field=models.CharField(blank=True, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="lieu_formation",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="longitude",
            field=models.CharField(blank=True, default="", max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="numero",
            field=models.CharField(blank=True, default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="precision_lieu",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="prestataire",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="tel_formateur",
            field=models.CharField(blank=True, default="", max_length=30),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="apprenant",
            name="ville_formation",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
    ]
