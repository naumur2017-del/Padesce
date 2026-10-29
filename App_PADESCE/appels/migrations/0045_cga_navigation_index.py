from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0044_appelcgaaudio")]

    operations = [
        migrations.AddIndex(
            model_name="appelcga",
            index=models.Index(
                fields=["source", "status", "raison_sociale"],
                condition=models.Q(is_active=True),
                name="cga_active_navigation_idx",
            ),
        ),
    ]
