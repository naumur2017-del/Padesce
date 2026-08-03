from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0036_appelpasformeii_formulaire")]
    operations = [migrations.AddField(model_name="appelpasformeii", name="est_forme", field=models.BooleanField(default=False))]
