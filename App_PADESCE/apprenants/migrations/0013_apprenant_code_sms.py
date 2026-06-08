from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("apprenants", "0012_apprenant_c5_apprenant_c6"),
    ]

    operations = [
        migrations.AddField(
            model_name="apprenant",
            name="code_sms",
            field=models.CharField(blank=True, db_index=True, max_length=20),
        ),
    ]
