from django.db import migrations


ROLE_GROUPS = {
    "manager_padesce": [
        "view_appel",
        "change_appel",
    ],
    "manager_cga": [
        "view_appelcga",
        "change_appelcga",
    ],
}


def create_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, perm_codes in ROLE_GROUPS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        perms = Permission.objects.filter(codename__in=perm_codes)
        group.permissions.set(perms)


def remove_role_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=ROLE_GROUPS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_useractivity"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_role_groups, remove_role_groups),
    ]
