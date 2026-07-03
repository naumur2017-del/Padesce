from django.db import migrations


def _assign_vague1_prestations(apps, schema_editor):
    """
    Assign phase_id=1 (Vague 1) to classes belonging to the 64 specific prestations.
    These prestations are confirmed to be part of Vague 1 based on the business list.
    """
    Prestation = apps.get_model("formations", "Prestation")
    Classe = apps.get_model("formations", "Classe")

    # List of 64 prestation codes that belong to Vague 1
    # Note: Database uses UPPERCASE codes
    vague1_prestation_codes = [
        "PRESTA001", "PRESTA008", "PRESTA009", "PRESTA010", "PRESTA018", "PRESTA019",
        "PRESTA022", "PRESTA023", "PRESTA027", "PRESTA029", "PRESTA036", "PRESTA038",
        "PRESTA039", "PRESTA044", "PRESTA045", "PRESTA046", "PRESTA047", "PRESTA049",
        "PRESTA050", "PRESTA051", "PRESTA054", "PRESTA058", "PRESTA063", "PRESTA064",
        "PRESTA066", "PRESTA071", "PRESTA075", "PRESTA083", "PRESTA085", "PRESTA086",
        "PRESTA087", "PRESTA099", "PRESTA104", "PRESTA106", "PRESTA113", "PRESTA118",
        "PRESTA121", "PRESTA125", "PRESTA126", "PRESTA128", "PRESTA129", "PRESTA131",
        "PRESTA133", "PRESTA134", "PRESTA136", "PRESTA138", "PRESTA140", "PRESTA143",
        "PRESTA144", "PRESTA145", "PRESTA146", "PRESTA147", "PRESTA149", "PRESTA151",
        "PRESTA153", "PRESTA154", "PRESTA158", "PRESTA159", "PRESTA164", "PRESTA165",
        "PRESTA168", "PRESTA170", "PRESTA172", "PRESTA173",
    ]

    # Get the IDs of these prestations
    vague1_prestation_ids = list(
        Prestation.objects.filter(code__in=vague1_prestation_codes)
        .values_list("id", flat=True)
    )

    # Update phase_id to 1 for classes belonging to these prestations
    updated_count = Classe.objects.filter(
        prestation_id__in=vague1_prestation_ids
    ).update(phase_id=1)

    print(f"Updated {updated_count} classes to phase_id=1 (Vague 1)")


class Migration(migrations.Migration):

    dependencies = [
        ("formations", "0014_classe_melange_cohorte"),
    ]

    operations = [
        migrations.RunPython(_assign_vague1_prestations, migrations.RunPython.noop),
    ]
