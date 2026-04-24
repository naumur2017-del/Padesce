from __future__ import annotations

import os
from unittest.mock import patch

from django.test import SimpleTestCase

import App_PADESCE.settings as project_settings


class RuntimeSettingsRedisTests(SimpleTestCase):
    def _env(self, **overrides):
        defaults = {
            "PADESCE_CACHE_BACKEND": "",
            "PADESCE_CACHE_KEY_PREFIX": "",
            "PADESCE_CHANNEL_LAYER_BACKEND": "",
            "REDIS_URL": "",
            "PADESCE_REDIS_URL": "",
            "PADESCE_CHANNELS_REDIS_URL": "",
        }
        defaults.update(overrides)
        return patch.dict(os.environ, defaults, clear=False)

    def test_cache_settings_use_redis_when_url_is_present(self) -> None:
        with self._env(
            REDIS_URL="redis://redis.internal:6379/1",
            PADESCE_CACHE_KEY_PREFIX="padesce-prod",
        ):
            with patch.object(project_settings, "HAS_DJANGO_REDIS", True):
                cache_settings = project_settings._cache_settings_from_env()

        default_cache = cache_settings["default"]
        self.assertEqual(default_cache["BACKEND"], "django_redis.cache.RedisCache")
        self.assertEqual(default_cache["LOCATION"], "redis://redis.internal:6379/1")
        self.assertEqual(default_cache["KEY_PREFIX"], "padesce-prod")
        self.assertEqual(
            default_cache["OPTIONS"]["CLIENT_CLASS"],
            "django_redis.client.DefaultClient",
        )

    def test_cache_settings_raise_if_redis_backend_is_requested_without_dependency(self) -> None:
        with self._env(PADESCE_CACHE_BACKEND="redis", REDIS_URL="redis://redis.internal:6379/1"):
            with patch.object(project_settings, "HAS_DJANGO_REDIS", False):
                with self.assertRaisesMessage(RuntimeError, "django-redis"):
                    project_settings._cache_settings_from_env()

    def test_channel_layers_use_redis_when_url_is_present(self) -> None:
        with self._env(
            PADESCE_REDIS_URL="redis://redis.internal:6379/1",
            PADESCE_CHANNELS_REDIS_URL="redis://redis.internal:6379/2",
        ):
            with patch.object(project_settings, "HAS_CHANNELS_REDIS", True):
                channel_layers = project_settings._channel_layers_from_env()

        default_layer = channel_layers["default"]
        self.assertEqual(default_layer["BACKEND"], "channels_redis.core.RedisChannelLayer")
        self.assertEqual(default_layer["CONFIG"]["hosts"], ["redis://redis.internal:6379/2"])

    def test_channel_layers_can_be_forced_to_memory(self) -> None:
        with self._env(
            REDIS_URL="redis://redis.internal:6379/1",
            PADESCE_CHANNEL_LAYER_BACKEND="memory",
        ):
            channel_layers = project_settings._channel_layers_from_env()

        self.assertEqual(
            channel_layers["default"]["BACKEND"],
            "channels.layers.InMemoryChannelLayer",
        )
