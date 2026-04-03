from django.contrib.auth.hashers import make_password
from django.db import migrations


YANAVA_USERNAME = "yanava"
YANAVA_PASSWORD = "PADESCE1234"
YANAVA_GROUPS = ("manager_padesce",)


def ensure_public_analysis_user(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")

    user, _ = User.objects.get_or_create(username=YANAVA_USERNAME)
    user.is_active = True
    user.password = make_password(YANAVA_PASSWORD)
    user.save(update_fields=["is_active", "password"])

    groups = []
    for group_name in YANAVA_GROUPS:
        group, _ = Group.objects.get_or_create(name=group_name)
        groups.append(group)
    if groups:
        user.groups.add(*groups)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_dashboard_manager_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(ensure_public_analysis_user, migrations.RunPython.noop),
    ]
