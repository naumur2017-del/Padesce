import logging
import threading
from urllib.parse import urlsplit
from typing import Optional

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import resolve_url
from django.urls import get_script_prefix, reverse, set_script_prefix
from django.utils import timezone

from App_PADESCE.core import error_views
from App_PADESCE.core.models import UserActivity

_thread_locals = threading.local()
logger = logging.getLogger(__name__)
PATH_PREFIX_ALIASES = ("/padesce",)


def _normalize_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""
    return prefix if prefix.startswith("/") else f"/{prefix}"


def detect_path_prefix(path: str | None) -> str:
    normalized = _normalize_prefix(path or "/") or "/"
    for prefix in PATH_PREFIX_ALIASES:
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return prefix
    return ""


def strip_path_prefix(path: str | None) -> str:
    normalized = _normalize_prefix(path or "/") or "/"
    matched_prefix = detect_path_prefix(normalized)
    if not matched_prefix:
        return normalized
    stripped = normalized[len(matched_prefix) :]
    if not stripped:
        return "/"
    return stripped if stripped.startswith("/") else f"/{stripped}"


def set_current_user(user):
    _thread_locals.user = user


def get_current_user():
    return getattr(_thread_locals, "user", None)


class PathPrefixMiddleware:
    """
    Prend en charge les URLs aliases montees sous /padesce sans casser les
    reverse() existants sur la racine.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        original_prefix = get_script_prefix()
        matched_prefix = detect_path_prefix(getattr(request, "path_info", "") or getattr(request, "path", ""))
        request.url_mount_prefix = matched_prefix
        if matched_prefix:
            set_script_prefix(f"{matched_prefix}/")
        try:
            response = self.get_response(request)
        finally:
            set_script_prefix(original_prefix)
        return response


class CurrentUserMiddleware:
    """
    Stocke l'utilisateur courant dans le thread local pour les signaux (audit).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        set_current_user(getattr(request, "user", None))
        response = self.get_response(request)
        return response


class FriendlyErrorPagesMiddleware:
    """
    Affiche des pages d'erreur sobres et stables en dev comme en production.
    """

    HANDLERS = {
        400: error_views.bad_request,
        403: error_views.permission_denied,
        404: error_views.page_not_found,
        500: error_views.server_error,
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        try:
            response = self.get_response(request)
        except Http404 as exc:
            return self._render_exception(request, 404, exc)
        except PermissionDenied as exc:
            return self._render_exception(request, 403, exc)
        except SuspiciousOperation as exc:
            logger.warning("Bad request on %s: %s", getattr(request, "path", ""), exc)
            return self._render_exception(request, 400, exc)
        except Exception:
            logger.exception("Unhandled application error on %s", getattr(request, "path", ""))
            return self._render_exception(request, 500, None)

        return self._normalize_response(request, response)

    def _render_exception(self, request: HttpRequest, status_code: int, exception):
        if error_views.request_prefers_json(request):
            return error_views.json_error_response(status_code)
        return self.HANDLERS[status_code](request, exception)

    def _normalize_response(self, request: HttpRequest, response):
        if response.headers.get("X-Friendly-Error-Page") == "1":
            return response
        if response.status_code not in self.HANDLERS:
            return response
        if error_views.request_prefers_json(request, response=response):
            return response
        if "text/html" not in str(response.headers.get("Content-Type", "text/html")).lower():
            return response
        return self.HANDLERS[response.status_code](request, None)


class LoginRequiredMiddleware:
    """
    Force l'authentification sur toutes les pages privees.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.user.is_authenticated:
            user = request.user
            path = strip_path_prefix(request.path_info or "/")
            try:
                is_consultant_only = (
                    not getattr(user, "is_superuser", False)
                    and user.groups.filter(name="consultant").exists()
                    and not user.groups.filter(name__in=["manager_padesce", "manager_cga"]).exists()
                )
            except Exception:
                is_consultant_only = False
            if is_consultant_only:
                allowed_prefixes = [
                    "/dashboard/",
                    "/consultant/",
                    "/deploiement/live/",
                    "/satisfaction-apprenants/analyse/",
                    "/accounts/logout/",
                    "/messages/support/",
                    "/guide-operateur/",
                    _normalize_prefix(getattr(settings, "STATIC_URL", "")),
                    _normalize_prefix(getattr(settings, "MEDIA_URL", "")),
                ]
                if path != "/dashboard/" and not any(path.startswith(p) for p in allowed_prefixes if p):
                    return HttpResponseRedirect(reverse("home"))
            return self.get_response(request)

        path = strip_path_prefix(request.path_info or "/")
        login_url = resolve_url(settings.LOGIN_URL or "login")
        login_path = strip_path_prefix(urlsplit(login_url).path) or "/"
        static_prefix = _normalize_prefix(getattr(settings, "STATIC_URL", ""))
        media_prefix = _normalize_prefix(getattr(settings, "MEDIA_URL", ""))

        exempt_prefixes = [
            "/accounts/",
            "/admin/",
            "/beneficiaire/",
            "/deploiement/live/",
            "/backup/api/trigger/",
            "/service-worker.js",
            "/manifest.webmanifest",
            static_prefix,
            media_prefix,
        ]
        if getattr(settings, "PUBLIC_CONSULTANT_ACCESS", False):
            exempt_prefixes.append("/consultant/")

        if path in ("/", login_path) or any(path.startswith(p) for p in exempt_prefixes if p):
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), login_url)


class UserActivityMiddleware:
    """
    Met a jour la derniere activite d'un utilisateur connecte.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            now = timezone.now()
            activity = UserActivity.objects.filter(user=user).first()
            if activity:
                if (now - activity.last_seen).total_seconds() > 60:
                    UserActivity.objects.filter(user=user).update(last_seen=now)
            else:
                UserActivity.objects.create(user=user, last_seen=now)
        response = self.get_response(request)
        return response
