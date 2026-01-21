from django.db import migrations, models

import App_PADESCE.appels.models


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appel",
            name="audio_file",
            field=models.FileField(blank=True, null=True, upload_to=App_PADESCE.appels.models.appel_audio_upload),
        ),
    ]
