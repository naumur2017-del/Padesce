from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apprenants", "0002_location_appartenance"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apprenant",
            name="telephone1",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name="apprenant",
            name="telephone2",
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
    ]
