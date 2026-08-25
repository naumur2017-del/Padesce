import os
from unittest.mock import patch

from django.test import SimpleTestCase

from App_PADESCE import settings as padesce_settings


class SessionSettingsTests(SimpleTestCase):
    def test_postgresql_without_shared_redis_uses_database_sessions(self):
        with (
            patch.object(
                padesce_settings,
                "DATABASES",
                {"default": {"ENGINE": "django.db.backends.postgresql"}},
            ),
            patch.object(padesce_settings, "_cache_backend_key_from_env", return_value="locmem"),
            patch.dict(os.environ, {"PADESCE_SESSION_ENGINE": ""}),
        ):
            self.assertEqual(
                padesce_settings._session_engine_from_env(),
                "django.contrib.sessions.backends.db",
            )

    def test_postgresql_with_redis_uses_cached_database_sessions(self):
        with (
            patch.object(
                padesce_settings,
                "DATABASES",
                {"default": {"ENGINE": "django.db.backends.postgresql"}},
            ),
            patch.object(padesce_settings, "_cache_backend_key_from_env", return_value="redis"),
            patch.dict(os.environ, {"PADESCE_SESSION_ENGINE": ""}),
        ):
            self.assertEqual(
                padesce_settings._session_engine_from_env(),
                "django.contrib.sessions.backends.cached_db",
            )
