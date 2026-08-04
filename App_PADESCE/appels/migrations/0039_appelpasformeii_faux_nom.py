from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0038_appelpasformeii_fenetre")]

    operations = [
        migrations.AddField(model_name="appelpasformeii", name="faux_nom", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="appelpasformeii", name="vrai_nom", field=models.CharField(blank=True, max_length=255)),
    ]
