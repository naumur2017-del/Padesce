from django.db import migrations


def remove_test_formateurs(apps, schema_editor):
    Formateur = apps.get_model("formations", "Formateur")
    targets = (
        "zap",
        "dieudonne yanava",
    )
    queryset = Formateur.objects.all()
    for target in targets:
        queryset.filter(nom__iexact=target).delete()
        queryset.filter(nom_complet__iexact=target).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0007_formateur_nom_from_excel"),
    ]

    operations = [
        migrations.RunPython(remove_test_formateurs, migrations.RunPython.noop),
    ]
