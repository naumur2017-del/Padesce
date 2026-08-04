from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0039_appelpasformeii_faux_nom")]

    operations = [
        migrations.AddField(
            model_name="appelpasformeii",
            name="pas_forme_du_tout",
            field=models.BooleanField(default=False),
        ),
    ]
