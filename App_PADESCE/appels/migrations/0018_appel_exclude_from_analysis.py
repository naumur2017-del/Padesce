from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0017_widen_fields_for_postgres_import"),
    ]

    operations = [
        migrations.AddField(
            model_name="appel",
            name="exclude_from_analysis",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
