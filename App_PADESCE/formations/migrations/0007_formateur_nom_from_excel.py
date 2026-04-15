from django.db import migrations, models


def fill_formateur_nom_from_excel(apps, schema_editor):
    Formateur = apps.get_model("formations", "Formateur")
    try:
        from App_PADESCE.appels.formateur_names import (
            FORMATEUR_NAME_FALLBACK,
            resolve_formateur_name_from_values,
        )
    except Exception:
        FORMATEUR_NAME_FALLBACK = "Non renseigné"
        resolve_formateur_name_from_values = None

    for formateur in Formateur.objects.all().only("id", "telephone", "nom_complet", "nom"):
        resolved = ""
        if resolve_formateur_name_from_values is not None:
            resolved = resolve_formateur_name_from_values(
                str(getattr(formateur, "telephone", "") or ""),
                str(getattr(formateur, "nom_complet", "") or ""),
            )
        target = str(resolved or "").strip() or FORMATEUR_NAME_FALLBACK
        if str(getattr(formateur, "nom", "") or "").strip() == target:
            continue
        formateur.nom = target
        formateur.save(update_fields=["nom"])


class Migration(migrations.Migration):
    dependencies = [
        ("formations", "0006_formateur_prestataire_prestation_ville"),
    ]

    operations = [
        migrations.AddField(
            model_name="formateur",
            name="nom",
            field=models.CharField(default="Non renseigné", max_length=255),
        ),
        migrations.RunPython(fill_formateur_nom_from_excel, migrations.RunPython.noop),
    ]
