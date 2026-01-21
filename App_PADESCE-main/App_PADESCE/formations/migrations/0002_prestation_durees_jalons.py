from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestation",
            name="duree_prevue_heures",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="prestation",
            name="duree_reelle_heures",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="prestation",
            name="jalons_contractuels",
            field=models.TextField(blank=True),
        ),
    ]
