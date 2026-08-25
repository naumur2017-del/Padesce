"""Shared-cache login throttling that never keys on an IP address alone."""

from __future__ import annotations

import hashlib
import hmac
import logging

from django.conf import settings
from django.core.cache import caches

from App_PADESCE.core.operator_auth import normalize_login_identifier


logger = logging.getLogger("App_PADESCE.auth")


class OperatorLoginAttemptLimiter:
    """Limit failures per normalized identifier *and* client address.

    Production activation requires a Redis cache. The local-cache exception is
    intentionally limited to tests, where it permits deterministic coverage.
    """

    cache_alias = "default"

    def is_blocked(self, request, identifier: str) -> bool:
        if not self._enabled():
            return False
        try:
            return int(self._cache().get(self._key(request, identifier), 0)) >= self._max_failures()
        except Exception:
            logger.exception("auth_event code=AUTH_THROTTLE_CACHE_UNAVAILABLE")
            return False

    def record_failure(self, request, identifier: str) -> None:
        if not self._enabled():
            return
        key = self._key(request, identifier)
        try:
            if self._cache().add(key, 1, timeout=self._window_seconds()):
                return
            self._cache().incr(key)
        except Exception:
            logger.exception("auth_event code=AUTH_THROTTLE_CACHE_UNAVAILABLE")

    def reset(self, request, identifier: str) -> None:
        if not self._enabled():
            return
        try:
            self._cache().delete(self._key(request, identifier))
        except Exception:
            logger.exception("auth_event code=AUTH_THROTTLE_CACHE_UNAVAILABLE")

    def _enabled(self) -> bool:
        if not getattr(settings, "PADESCE_AUTH_THROTTLE_ENABLED", False):
            return False
        if self._uses_shared_redis_cache():
            return True
        if getattr(settings, "PADESCE_AUTH_THROTTLE_ALLOW_LOCAL_CACHE_FOR_TESTS", False):
            return True
        logger.warning("auth_event code=AUTH_THROTTLE_SHARED_CACHE_REQUIRED")
        return False

    def _uses_shared_redis_cache(self) -> bool:
        backend = str(settings.CACHES[self.cache_alias].get("BACKEND", "")).lower()
        return "django_redis" in backend or "redis" in backend

    def _key(self, request, identifier: str) -> str:
        normalized_identifier = normalize_login_identifier(identifier)
        address = str(request.META.get("REMOTE_ADDR", "") or "")
        material = f"{normalized_identifier}\x00{address}".encode("utf-8")
        secret = str(
            getattr(settings, "PADESCE_AUTH_LOG_HASH_KEY", "") or settings.SECRET_KEY
        ).encode("utf-8")
        fingerprint = hmac.new(secret, material, hashlib.sha256).hexdigest()
        return f"padesce:auth:attempt:{fingerprint}"

    def _cache(self):
        return caches[self.cache_alias]

    @staticmethod
    def _max_failures() -> int:
        return max(1, int(getattr(settings, "PADESCE_AUTH_THROTTLE_MAX_FAILURES", 5)))

    @staticmethod
    def _window_seconds() -> int:
        return max(1, int(getattr(settings, "PADESCE_AUTH_THROTTLE_WINDOW_SECONDS", 900)))
