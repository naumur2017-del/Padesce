import threading
from typing import Optional

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest
from django.utils import timezone

from App_PADESCE.core.models import UserActivity

_thread_locals = threading.local()


def set_current_user(user):
    _thread_locals.user = user


def get_current_user():
    return getattr(_thread_locals, "user", None)


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


class LoginRequiredMiddleware:
    """
    Force l'authentification sur toutes les pages privees.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info or "/"
        login_url = settings.LOGIN_URL or "/"

        def _normalize_prefix(prefix: str | None) -> str:
            if not prefix:
                return ""
            return prefix if prefix.startswith("/") else f"/{prefix}"

        login_path = _normalize_prefix(login_url) or "/"
        static_prefix = _normalize_prefix(getattr(settings, "STATIC_URL", ""))
        media_prefix = _normalize_prefix(getattr(settings, "MEDIA_URL", ""))

        exempt_prefixes = [
            "/accounts/",
            "/admin/",
            "/beneficiaire/",
            static_prefix,
            media_prefix,
        ]

        if path in ("/", login_path) or any(path.startswith(p) for p in exempt_prefixes if p):
            return self.get_response(request)

        return redirect_to_login(request.get_full_path(), login_path)


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
