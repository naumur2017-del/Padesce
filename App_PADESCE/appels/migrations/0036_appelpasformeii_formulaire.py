from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("appels", "0035_appelpasformeii")]
    operations = [
        migrations.AddField(model_name="appelpasformeii", name="connait_structure", field=models.CharField(blank=True, max_length=3)),
        migrations.AddField(model_name="appelpasformeii", name="membre_structure", field=models.CharField(blank=True, max_length=3)),
        migrations.AddField(model_name="appelpasformeii", name="a_assiste_formation", field=models.CharField(blank=True, max_length=3)),
        migrations.AddField(model_name="appelpasformeii", name="connait_theme", field=models.CharField(blank=True, max_length=3)),
        migrations.AddField(model_name="appelpasformeii", name="commentaire", field=models.TextField(blank=True)),
        migrations.AddField(model_name="appelpasformeii", name="rappel_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="appelpasformeii", name="audio_file", field=models.FileField(blank=True, max_length=255, null=True, upload_to="pas-forme-ii/")),
    ]
