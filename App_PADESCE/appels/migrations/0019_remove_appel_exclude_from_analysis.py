from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0018_appel_exclude_from_analysis"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="appel",
            name="exclude_from_analysis",
        ),
    ]
