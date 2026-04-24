from django.db import migrations, models


class AddFieldUnlessSQLite(migrations.AddField):
    """
    This field only lives for one migration before being removed again.
    Skipping the SQLite schema change avoids rebuilding appels_appel on
    legacy local databases that already have fragile foreign key metadata.
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
        ("appels", "0017_widen_fields_for_postgres_import"),
    ]

    operations = [
        AddFieldUnlessSQLite(
            model_name="appel",
            name="exclude_from_analysis",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
