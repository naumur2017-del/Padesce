from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "App_PADESCE.core"

    def ready(self) -> None:
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group, update_last_login

        import App_PADESCE.core.cache_signals  # noqa: F401
        import App_PADESCE.core.deployment_live  # noqa: F401
        import App_PADESCE.core.signals  # noqa: F401

        # Register signal handlers / cache invalidation.
        App_PADESCE.core.cache_signals.setup_cache_signals()

        try:
            default_db = settings.DATABASES.get("default", {})
            if default_db.get("ENGINE") == "django.db.backends.sqlite3":
                user_logged_in.disconnect(
                    update_last_login,
                    sender=get_user_model(),
                    dispatch_uid="update_last_login",
                )
        except Exception:
            pass

        def ensure_roles(sender, **kwargs):
            Group.objects.get_or_create(name="consultant")

        post_migrate.connect(ensure_roles, sender=self)

        return super().ready()
