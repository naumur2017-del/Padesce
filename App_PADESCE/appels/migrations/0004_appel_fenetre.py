from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0003_appel_deja_forme_appel_formation_padesce_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="appel",
            name="fenetre",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
