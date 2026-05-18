from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0028_callalert"),
    ]

    operations = [
        migrations.AddField(
            model_name="appelcga",
            name="source",
            field=models.CharField(
                choices=[("entreprise", "Entreprise"), ("cabinet", "Cabinet")],
                db_index=True,
                default="entreprise",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="appelcga",
            name="telephone",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddIndex(
            model_name="appelcga",
            index=models.Index(
                fields=["source", "is_active", "status"],
                name="appelcga_source_active_idx",
            ),
        ),
    ]
