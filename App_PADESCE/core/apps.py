from django.apps import AppConfig
from django.db.models.signals import post_migrate


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_PADESCE.core'

    def ready(self) -> None:
        import App_PADESCE.core.deployment_live  # noqa: F401
        # Register signal handlers for audit logging.
        import App_PADESCE.core.signals  # noqa: F401
        from django.contrib.auth.models import Group

        def ensure_roles(sender, **kwargs):
            Group.objects.get_or_create(name="consultant")

        post_migrate.connect(ensure_roles, sender=self)
        return super().ready()
