from __future__ import annotations

import time

from django.core.cache import cache

_CACHE_VERSION_PREFIX = "analysis-cache-version"


def _scope_key(scope: str) -> str:
    normalized_scope = str(scope or "global").strip() or "global"
    return f"{_CACHE_VERSION_PREFIX}:{normalized_scope}"


def get_analysis_cache_version(scope: str) -> str:
    cache_key = _scope_key(scope)
    value = cache.get(cache_key)
    if value is None:
        value = "1"
        cache.set(cache_key, value, timeout=None)
    return str(value)


def bump_analysis_cache_version(*scopes: str) -> None:
    version = str(time.time_ns())
    for scope in scopes or ("global",):
        cache.set(_scope_key(scope), version, timeout=None)
