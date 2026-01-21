from django.db import migrations


GROUPS = {
    "admin_systeme": {
        "all_permissions": True,
    },
    "inspecteur_enqueteur": {
        "perms": [
            "add_presence",
            "change_presence",
            "view_presence",
            "add_satisfactionapprenant",
            "change_satisfactionapprenant",
            "view_satisfactionapprenant",
            "add_satisfactionformateur",
            "change_satisfactionformateur",
            "view_satisfactionformateur",
            "add_enqueteenvironnement",
            "change_enqueteenvironnement",
            "view_enqueteenvironnement",
        ],
    },
    "prestataire_beneficiaire": {
        "perms": [
            "view_presence",
            "view_satisfactionapprenant",
            "view_satisfactionformateur",
            "view_enqueteenvironnement",
            "view_classe",
            "view_formation",
            "view_prestation",
            "view_prestataire",
            "view_beneficiaire",
            "view_lieu",
        ],
    },
    "consultation": {
        "perms": [
            "view_presence",
            "view_satisfactionapprenant",
            "view_satisfactionformateur",
            "view_enqueteenvironnement",
            "view_apprenant",
            "view_classe",
            "view_formation",
            "view_prestation",
            "view_prestataire",
            "view_beneficiaire",
            "view_lieu",
            "view_formateur",
            "view_inspecteur",
            "view_contact",
            "view_campagnemessage",
        ],
    },
}


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, cfg in GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        if cfg.get("all_permissions"):
            perms = Permission.objects.all()
        else:
            perm_codes = cfg.get("perms", [])
            perms = Permission.objects.filter(codename__in=perm_codes)
        group.permissions.set(perms)


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=GROUPS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
