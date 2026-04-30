from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    _get_backends,
    _get_user_session_key,
)
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect
from django.middleware.csrf import rotate_token
from django.utils.crypto import constant_time_compare


def _sqlite_safe_auth_login(request, user, backend=None):
    session_auth_hash = ""
    if user is None:
        user = request.user
    if hasattr(user, "get_session_auth_hash"):
        session_auth_hash = user.get_session_auth_hash()

    if SESSION_KEY in request.session:
        if _get_user_session_key(request) != user.pk or (
            session_auth_hash
            and not constant_time_compare(
                request.session.get(HASH_SESSION_KEY, ""), session_auth_hash
            )
        ):
            request.session.flush()
    else:
        request.session.cycle_key()

    try:
        backend = backend or user.backend
    except AttributeError:
        backends = _get_backends(return_tuples=True)
        if len(backends) == 1:
            _, backend = backends[0]
        else:
            raise ValueError(
                "Multiple authentication backends are configured; "
                "the backend argument is required."
            )
    else:
        if not isinstance(backend, str):
            raise TypeError(f"backend must be a dotted import path string (got {backend!r}).")

    request.session[SESSION_KEY] = user._meta.pk.value_to_string(user)
    request.session[BACKEND_SESSION_KEY] = backend
    request.session[HASH_SESSION_KEY] = session_auth_hash
    if hasattr(request, "user"):
        request.user = user
    rotate_token(request)


class SQLiteSafeLoginView(LoginView):
    def form_valid(self, form):
        user = form.get_user()
        default_db = settings.DATABASES.get("default", {})
        if default_db.get("ENGINE") != "django.db.backends.sqlite3":
            return super().form_valid(form)
        _sqlite_safe_auth_login(self.request, user)
        return HttpResponseRedirect(self.get_success_url())
