import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "App_PADESCE.core"

    def ready(self) -> None:
        from django.conf import settings
        from django.contrib.auth.models import Group

        import App_PADESCE.core.deployment_live  # noqa: F401

        # Register signal handlers for audit logging.
        import App_PADESCE.core.signals  # noqa: F401

        def ensure_roles(sender, **kwargs):
            Group.objects.get_or_create(name="consultant")

        post_migrate.connect(ensure_roles, sender=self)

        # One-off DB update for Audio Transcription Priorities
        marker_path = os.path.join(settings.BASE_DIR, ".db_priority_updated_v1")
        if not os.path.exists(marker_path):
            try:
                from update_db_priorities import run_db_priority_update

                run_db_priority_update()
                with open(marker_path, "w") as f:
                    f.write("done")
            except Exception as e:
                print(f"Error during startup DB priority update: {str(e)}")

        return super().ready()
