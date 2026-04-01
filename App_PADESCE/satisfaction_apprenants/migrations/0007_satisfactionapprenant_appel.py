from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0013_appel_flag_deja_appele_appel_flag_faux_nom_and_more"),
        ("satisfaction_apprenants", "0006_rename_q3_rythme_formation_satisfactionapprenant_q3_maitrise_contenu_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="satisfactionapprenant",
            name="appel",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="satisfaction_apprenant",
                to="appels.appel",
            ),
        ),
    ]
