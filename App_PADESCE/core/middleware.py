import logging
import threading
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import OperationalError, ProgrammingError
from django.http import Http404, HttpRequest, HttpResponseRedirect
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


def _iter_public_analysis_auto_login_prefixes() -> tuple[str, ...]:
    configured = getattr(settings, "PUBLIC_ANALYSIS_AUTO_LOGIN_PREFIXES", ())
    if isinstance(configured, str):
        raw_values = configured.split(",")
    else:
        raw_values = configured
    prefixes = []
    for value in raw_values:
        normalized = _normalize_prefix(str(value).strip())
        if normalized:
            prefixes.append(normalized)
    return tuple(prefixes)


def _is_public_analysis_auto_login_path(path: str) -> bool:
    if any(p in path for p in ["/api/", "/import/", "/delete/", "/upload/", "/action/", "/finalize/"]):
        return False
    return any(path.startswith(prefix) for prefix in _iter_public_analysis_auto_login_prefixes())


def _try_public_analysis_auto_login(request: HttpRequest, path: str) -> bool:
    if request.user.is_authenticated:
        return False
    if not getattr(settings, "PUBLIC_ANALYSIS_AUTO_LOGIN", False):
        return False
    if not _is_public_analysis_auto_login_path(path):
        return False

    username = str(getattr(settings, "PUBLIC_ANALYSIS_AUTO_LOGIN_USERNAME", "") or "").strip()
    password = str(getattr(settings, "PUBLIC_ANALYSIS_AUTO_LOGIN_PASSWORD", "") or "")
    if not username or not password:
        logger.warning("Public analysis auto-login is enabled but credentials are incomplete.")
        return False

    user = authenticate(request, username=username, password=password)
    if user is None:
        logger.warning(
            "Public analysis auto-login failed for user '%s' on %s.",
            username,
            path,
        )
        return False

    login(request, user)
    request.user = user
    return True


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
        matched_prefix = detect_path_prefix(
            getattr(request, "path_info", "") or getattr(request, "path", "")
        )
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
        path = strip_path_prefix(request.path_info or "/")
        if _try_public_analysis_auto_login(request, path):
            return self.get_response(request)

        if request.user.is_authenticated:
            user = request.user
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
                    "/deploiement/live-status/",
                    "/reporting/documentation/",
                    "/satisfaction-apprenants/analyse/",
                    "/accounts/logout/",
                    "/messages/support/",
                    "/guide-operateur/",
                    "/api/",
                    _normalize_prefix(getattr(settings, "STATIC_URL", "")),
                    _normalize_prefix(getattr(settings, "MEDIA_URL", "")),
                ]
                if path not in {"/", "/dashboard/"} and not any(
                    path.startswith(p) for p in allowed_prefixes if p
                ):
                    return HttpResponseRedirect(reverse("home"))
            return self.get_response(request)

        login_url = resolve_url(settings.LOGIN_URL or "login")
        login_path = strip_path_prefix(urlsplit(login_url).path) or "/"
        static_prefix = _normalize_prefix(getattr(settings, "STATIC_URL", ""))
        media_prefix = _normalize_prefix(getattr(settings, "MEDIA_URL", ""))

        exempt_prefixes = [
            "/accounts/",
            "/admin/",
            "/beneficiaire/",
            "/apprenants/",
            "/classe/",
            "/prestation/",
            "/analyse/appels/apprenant/",
            "/analyse/appels/formateur/",
            "/deploiement/live/",
            "/deploiement/live-status/",
            "/backup/api/trigger/",
            "/service-worker.js",
            "/manifest.webmanifest",
            static_prefix,
            media_prefix,
        ]
        public_token_api_prefixes = [
            "/backup/api/trigger/",
            "/backup/api/trigger-status/",
            "/reporting/api/daily-digest/trigger/",
        ]
        exempt_prefixes.extend(public_token_api_prefixes)
        if getattr(settings, "PUBLIC_CONSULTANT_ACCESS", False):
            exempt_prefixes.append("/consultant/")

        # Keep apprenant/formateur analysis detail popups public even when the app is
        # exposed behind an extra URL prefix (reverse proxy, subpath deployment, etc.).
        if "/analyse/appels/apprenant/" in path or "/analyse/appels/formateur/" in path:
            return self.get_response(request)

        if path in ("/", login_path) or any(path.startswith(p) for p in exempt_prefixes if p):
            # Safety: even if a prefix is exempt, block sensitive actions for anonymous users
            if any(p in path for p in ["/api/", "/import/", "/delete/", "/upload/", "/action/", "/finalize/"]) and not any(path.startswith(p) for p in public_token_api_prefixes):
                return redirect_to_login(request.get_full_path(), login_url)
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), login_url)


def _get_client_ip(request: HttpRequest) -> str:
    """Retourne l'IP réelle du client (supporte les proxys)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or ""


def _fetch_ip_geolocation(ip: str) -> dict:
    """Appel synchrone à ip-api.com. Retourne un dict avec lat/lon/city/country."""
    import json as _json
    import urllib.request

    if not ip or ip in ("127.0.0.1", "::1") or ip.startswith("192.168.") or ip.startswith("10."):
        return {"lat": None, "lon": None, "city": "Local", "country": "Local"}
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,country"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = _json.loads(resp.read().decode())
        if data.get("status") == "success":
            return {
                "lat": data.get("lat"),
                "lon": data.get("lon"),
                "city": data.get("city", ""),
                "country": data.get("country", ""),
            }
    except Exception:
        pass
    return {"lat": None, "lon": None, "city": "", "country": ""}


def _update_activity_with_geo(user_id: int, ip: str, now):
    """Mise à jour en arrière-plan : géolocalisation + sauvegarde."""
    try:
        geo = _fetch_ip_geolocation(ip)
        activity = UserActivity.objects.filter(user_id=user_id).first()
        if not activity:
            return
        next_lat = geo["lat"] if geo["lat"] is not None else activity.last_latitude
        next_lon = geo["lon"] if geo["lon"] is not None else activity.last_longitude
        next_city = (geo["city"] or "").strip() or activity.last_city
        next_country = (geo["country"] or "").strip() or activity.last_country
        UserActivity.objects.filter(user_id=user_id).update(
            last_seen=now,
            last_ip=ip or None,
            last_latitude=next_lat,
            last_longitude=next_lon,
            last_city=next_city,
            last_country=next_country,
        )
        # Enregistrer dans l'historique des connexions
        from App_PADESCE.core.models import UserLoginLog

        UserLoginLog.objects.create(
            user_id=user_id,
            ip_address=ip or None,
            latitude=next_lat,
            longitude=next_lon,
            city=next_city,
            country=next_country,
        )
    except Exception:
        pass


class UserActivityMiddleware:
    """
    Met a jour la derniere activite d'un utilisateur connecte.
    Capture également l'adresse IP et la géolocalisation (lat/lon).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            try:
                now = timezone.now()
                ip = _get_client_ip(request)
                activity = UserActivity.objects.filter(user=user).first()
                if activity:
                    delta = (now - activity.last_seen).total_seconds()
                    if delta > 60:
                        # Mise à jour rapide de last_seen, géo en arrière-plan
                        UserActivity.objects.filter(user=user).update(last_seen=now)
                        t = threading.Thread(
                            target=_update_activity_with_geo,
                            args=(user.pk, ip, now),
                            daemon=True,
                        )
                        t.start()
                else:
                    UserActivity.objects.create(user=user, last_seen=now, last_ip=ip or None)
                    t = threading.Thread(
                        target=_update_activity_with_geo,
                        args=(user.pk, ip, now),
                        daemon=True,
                    )
                    t.start()
            except (OperationalError, ProgrammingError):
                logger.warning(
                    "UserActivity tracking skipped because the database schema is not up to date.",
                    exc_info=True,
                )
        response = self.get_response(request)
        return response
