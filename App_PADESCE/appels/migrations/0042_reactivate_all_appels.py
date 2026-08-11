from django.db import migrations


def reactivate_all_appels(apps, schema_editor):
    Appel = apps.get_model("appels", "Appel")
    Appel.objects.filter(is_active=False).update(is_active=True)


class Migration(migrations.Migration):

    dependencies = [
        ("appels", "0041_merge_appelpasformeii_fields"),
    ]

    operations = [
        migrations.RunPython(reactivate_all_appels, migrations.RunPython.noop),
    ]
