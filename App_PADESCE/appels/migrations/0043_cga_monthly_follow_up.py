from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0042_reactivate_all_appels"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appelcga",
            name="niu",
            field=models.CharField(max_length=64),
        ),
        migrations.AlterField(
            model_name="appelcga",
            name="source",
            field=models.CharField(
                choices=[
                    ("entreprise", "Entreprise"),
                    ("cabinet", "Cabinet"),
                    ("suivi", "Suivi CGA"),
                ],
                db_index=True,
                default="entreprise",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="appelcga",
            name="campaign_month",
            field=models.DateField(
                blank=True,
                db_index=True,
                help_text="Premier jour du mois pour les campagnes Suivi CGA.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="appelcga",
            index=models.Index(
                fields=["source", "campaign_month"],
                name="appelcga_source_month_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="appelcga",
            constraint=models.UniqueConstraint(
                fields=("source", "campaign_month", "niu"),
                name="appelcga_source_month_niu_uniq",
            ),
        ),
    ]
