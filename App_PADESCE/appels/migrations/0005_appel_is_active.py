from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0004_appel_fenetre"),
    ]

    operations = [
        migrations.AddField(
            model_name="appel",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
    ]
