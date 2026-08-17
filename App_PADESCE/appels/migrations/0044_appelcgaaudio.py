from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from App_PADESCE.appels.models import appel_cga_history_audio_upload


def copy_existing_cga_audios(apps, schema_editor):
    AppelCGA = apps.get_model("appels", "AppelCGA")
    AppelCGAAudio = apps.get_model("appels", "AppelCGAAudio")
    batch = []
    for appel_id, audio_name in AppelCGA.objects.exclude(audio_file="").values_list("id", "audio_file"):
        batch.append(AppelCGAAudio(appel_id=appel_id, audio_file=audio_name))
    if batch:
        AppelCGAAudio.objects.bulk_create(batch, batch_size=2000)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("appels", "0043_cga_monthly_follow_up"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppelCGAAudio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("audio_file", models.FileField(max_length=255, upload_to=appel_cga_history_audio_upload)),
                ("appel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="audio_history", to="appels.appelcga")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cga_audio_uploads", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.RunPython(copy_existing_cga_audios, migrations.RunPython.noop),
    ]
