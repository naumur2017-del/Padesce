from __future__ import annotations

from functools import lru_cache
from importlib import import_module


@lru_cache(maxsize=None)
def _resolve_view(dotted_path: str):
    module_path, attr_name = dotted_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, attr_name)


def lazy_view(dotted_path: str):
    def _wrapped(request, *args, **kwargs):
        view = _resolve_view(dotted_path)
        return view(request, *args, **kwargs)

    _wrapped.__name__ = f"lazy_{dotted_path.rsplit('.', 1)[-1]}"
    _wrapped.__qualname__ = _wrapped.__name__
    _wrapped.__module__ = __name__
    return _wrapped
