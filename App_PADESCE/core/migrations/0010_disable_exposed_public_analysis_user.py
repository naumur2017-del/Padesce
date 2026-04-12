from django.contrib.auth.hashers import check_password
from django.db import migrations


YANAVA_USERNAME = "yanava"
YANAVA_PASSWORD = "PADESCE1234"


def disable_exposed_public_analysis_user(apps, schema_editor):
    User = apps.get_model("auth", "User")
    user = User.objects.filter(username=YANAVA_USERNAME).first()
    if not user:
        return
    if not check_password(YANAVA_PASSWORD, user.password):
        return
    user.password = "!"
    user.is_active = False
    user.save(update_fields=["password", "is_active"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_rename_core_userac_user_id_aa8d99_idx_core_userac_user_id_0cac8f_idx_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(disable_exposed_public_analysis_user, migrations.RunPython.noop),
    ]
