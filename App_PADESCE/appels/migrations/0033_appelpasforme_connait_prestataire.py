from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0032_pasforme_prestatairedemarrage_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="appelpasforme",
            name="connait_prestataire",
            field=models.CharField(
                blank=True, choices=[("OUI", "Oui"), ("NON", "Non")], max_length=3
            ),
        ),
    ]
