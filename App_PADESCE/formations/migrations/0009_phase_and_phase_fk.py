from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0008_remove_test_formateurs_zap_yanava"),
    ]

    operations = [
        migrations.CreateModel(
            name="Phase",
            fields=[
                ("id_phase", models.AutoField(db_column="ID_Phase", primary_key=True, serialize=False)),
                ("date_debut", models.DateField()),
                ("date_fin", models.DateField(blank=True, null=True)),
            ],
            options={
                "ordering": ["id_phase"],
            },
        ),
        migrations.AddField(
            model_name="classe",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="classes",
                to="formations.phase",
            ),
        ),
        migrations.AddField(
            model_name="formateur",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="formateurs",
                to="formations.phase",
            ),
        ),
        migrations.AddField(
            model_name="prestation",
            name="phase",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="prestations",
                to="formations.phase",
            ),
        ),
    ]
