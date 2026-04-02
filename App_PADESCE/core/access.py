from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

ANALYSIS_GROUP_NAMES = ("manager_padesce", "manager_cga", "consultant")
ANALYSIS_ACCESS_MESSAGE = "Acces reserve aux superadmins et aux managers PADESCE/CGA."
SUPERADMIN_ACCESS_MESSAGE = "Action reservee au superadmin."
CONSULTANT_ACCESS_MESSAGE = "Acces reserve au role consultant."


def _is_authenticated(user) -> bool:
    return bool(user and getattr(user, "is_authenticated", False))


def public_consultant_access_enabled() -> bool:
    return bool(getattr(settings, "PUBLIC_CONSULTANT_ACCESS", False))


def has_analysis_access(user) -> bool:
    if not _is_authenticated(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    groups = getattr(user, "groups", None)
    if groups is None:
        return False
    try:
        return groups.filter(name__in=ANALYSIS_GROUP_NAMES).exists()
    except Exception:
        return False


def has_superadmin_access(user) -> bool:
    return bool(_is_authenticated(user) and getattr(user, "is_superuser", False))


def has_consultant_access(user) -> bool:
    if not _is_authenticated(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    groups = getattr(user, "groups", None)
    if groups is None:
        return False
    try:
        return groups.filter(name="consultant").exists()
    except Exception:
        return False


def _expects_json(request) -> bool:
    headers = getattr(request, "headers", {})
    accept = str(headers.get("Accept", ""))
    requested_with = str(headers.get("X-Requested-With", ""))
    content_type = str(getattr(request, "content_type", "") or request.META.get("CONTENT_TYPE", ""))
    path = str(getattr(request, "path", "") or "")
    return (
        requested_with.lower() == "xmlhttprequest"
        or "application/json" in accept.lower()
        or "application/json" in content_type.lower()
        or path.startswith("/reporting/api/")
        or path.endswith("/analyse/rag/")
        or path.endswith("/api/excel-reseau/")
    )


def _deny(request, message: str):
    if _expects_json(request):
        return JsonResponse({"error": message}, status=403)
    raise PermissionDenied(message)


def _access_guard(view_func, predicate, denied_message: str):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not _is_authenticated(user):
            return redirect_to_login(
                request.get_full_path(), redirect_field_name=REDIRECT_FIELD_NAME
            )
        if not predicate(user):
            return _deny(request, denied_message)
        return view_func(request, *args, **kwargs)

    return wrapped


def require_analysis_access(view_func):
    return _access_guard(view_func, has_analysis_access, ANALYSIS_ACCESS_MESSAGE)


def require_superadmin_access(view_func):
    return _access_guard(view_func, has_superadmin_access, SUPERADMIN_ACCESS_MESSAGE)


def require_consultant_access(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if public_consultant_access_enabled():
            return view_func(request, *args, **kwargs)

        user = getattr(request, "user", None)
        if not _is_authenticated(user):
            return redirect_to_login(
                request.get_full_path(), redirect_field_name=REDIRECT_FIELD_NAME
            )
        if not has_consultant_access(user):
            return _deny(request, CONSULTANT_ACCESS_MESSAGE)
        return view_func(request, *args, **kwargs)

    return wrapped
