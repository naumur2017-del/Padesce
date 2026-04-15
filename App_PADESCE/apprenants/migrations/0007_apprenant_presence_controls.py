from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("apprenants", "0006_import_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="apprenant",
            name="c1",
            field=models.CharField(
                choices=[("PR", "Present"), ("AB", "Absent")], 
                default="AB", max_length=2
            ),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="c2",
            field=models.CharField(
                choices=[("PR", "Present"), ("AB", "Absent")], 
                default="AB", max_length=2
            ),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="c3",
            field=models.CharField(
                choices=[("PR", "Present"), ("AB", "Absent")], 
                default="AB", max_length=2
            ),
        ),
        migrations.AddField(
            model_name="apprenant",
            name="c4",
            field=models.CharField(
                choices=[("PR", "Present"), ("AB", "Absent")], 
                default="AB", max_length=2
            ),
        ),
    ]
