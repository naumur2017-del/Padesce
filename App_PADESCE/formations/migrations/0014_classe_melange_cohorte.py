from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0013_seed_presence_inspecteurs"),
    ]

    operations = [
        migrations.AddField(
            model_name="classe",
            name="melange_cohorte",
            field=models.BooleanField(default=False),
        ),
    ]
