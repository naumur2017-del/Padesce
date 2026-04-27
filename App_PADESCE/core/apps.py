from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "App_PADESCE.core"

    def ready(self) -> None:
        from django.contrib.auth.models import Group

        import App_PADESCE.core.deployment_live  # noqa: F401

        # Register signal handlers for audit logging.
        import App_PADESCE.core.signals  # noqa: F401
        
        # Register cache invalidation signals
        import App_PADESCE.core.cache_signals  # noqa: F401
        App_PADESCE.core.cache_signals.setup_cache_signals()

        def ensure_roles(sender, **kwargs):
            Group.objects.get_or_create(name="consultant")

        post_migrate.connect(ensure_roles, sender=self)

        return super().ready()
