from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_PADESCE.core'

    def ready(self) -> None:
        # Register signal handlers for audit logging.
        import App_PADESCE.core.signals  # noqa: F401
        return super().ready()
