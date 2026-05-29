from django.test import SimpleTestCase

from App_PADESCE.core.gandi_deploy import APP_ENV_SYNC_KEYS


class GandiEmailSyncTests(SimpleTestCase):
    def test_app_env_sync_keys_include_backup_and_report_email_settings(self) -> None:
        expected_keys = {
            "BACKUP_TRIGGER_TOKEN",
            "REPORT_TRIGGER_TOKEN",
            "BACKUP_RETENTION_DAYS",
            "HUGGINGFACE_TOKEN",
            "HUGGINGFACE_SPACE_REPO_ID",
            "HUGGINGFACE_SPACE_DB_PATH",
            "HUGGINGFACE_BACKUP_SYNC_ENABLED",
            "HUGGINGFACE_BACKUP_SYNC_REQUIRED",
            "PADESCE_CHAT_API_URL",
            "EMAIL_BACKEND",
            "EMAIL_HOST",
            "EMAIL_PORT",
            "EMAIL_USE_TLS",
            "EMAIL_USE_SSL",
            "EMAIL_TIMEOUT",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "DEFAULT_FROM_EMAIL",
            "REPORT_EMAIL_TO",
            "DEPLOYMENT_REPORT_EMAIL_TO",
        }

        for key in expected_keys:
            self.assertIn(key, APP_ENV_SYNC_KEYS)
