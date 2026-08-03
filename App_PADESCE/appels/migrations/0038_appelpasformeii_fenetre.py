from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0037_appelpasformeii_est_forme")]

    operations = [
        migrations.AddField(
            model_name="appelpasformeii",
            name="fenetre",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
    ]
