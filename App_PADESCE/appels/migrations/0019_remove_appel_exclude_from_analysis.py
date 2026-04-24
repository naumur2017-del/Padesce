from django.db import migrations


class RemoveFieldUnlessSQLite(migrations.RemoveField):
    """
    On SQLite, keep this migration as a state-only change. The transient
    column is never used by later code, and skipping the table rebuild
    avoids foreign key mismatch failures on older local databases.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "sqlite":
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor == "sqlite":
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    dependencies = [
        ("appels", "0018_appel_exclude_from_analysis"),
    ]

    operations = [
        RemoveFieldUnlessSQLite(
            model_name="appel",
            name="exclude_from_analysis",
        ),
    ]
