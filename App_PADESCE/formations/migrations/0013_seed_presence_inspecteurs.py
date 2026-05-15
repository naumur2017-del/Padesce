from django.db import migrations


def seed_presence_inspecteurs(apps, schema_editor):
    Inspecteur = apps.get_model("formations", "Inspecteur")
    for index in range(1, 11):
        code = f"INS{index:03d}"
        Inspecteur.objects.update_or_create(
            code=code,
            defaults={"nom_complet": f"Inspecteur{index}", "actif": True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0012_update_phase_data"),
    ]

    operations = [
        migrations.RunPython(seed_presence_inspecteurs, noop_reverse),
    ]
