"""Feature-flagged backend for operator authentication.

The backend is deliberately not enabled by default. Before activation, the
authorized groups must be explicitly configured and the account audit must
have been reviewed by a human.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from App_PADESCE.core.operator_auth import normalize_login_identifier


logger = logging.getLogger("App_PADESCE.auth")


def _required_group_names(value: object) -> frozenset[str]:
    if isinstance(value, str):
        values: Iterable[object] = value.split(",")
    elif isinstance(value, Iterable):
        values = value
    else:
        values = ()
    return frozenset(str(item).strip() for item in values if str(item).strip())


class OperatorAuthenticationBackend(ModelBackend):
    """Authenticate only one unambiguous, active user with an allowed group."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        started_at = time.monotonic()
        user_model = get_user_model()
        supplied_identifier = username if username is not None else kwargs.get(user_model.USERNAME_FIELD)
        normalized_identifier = normalize_login_identifier(supplied_identifier)
        if not normalized_identifier or password is None:
            self._log("AUTH_IDENTIFIER_EMPTY", request, started_at)
            return None

        required_groups = _required_group_names(
            getattr(settings, "PADESCE_OPERATOR_LOGIN_REQUIRED_GROUPS", ())
        )
        if not required_groups:
            self._consume_password_timing(password)
            self._log("AUTH_ROLE_CONFIG_MISSING", request, started_at)
            return None

        try:
            candidates = [
                user
                for user in user_model._default_manager.all().prefetch_related("groups")
                if normalize_login_identifier(getattr(user, user_model.USERNAME_FIELD, ""))
                == normalized_identifier
            ]
        except Exception:
            self._consume_password_timing(password)
            self._log("AUTH_INTERNAL_ERROR", request, started_at, exc_info=True)
            return None

        if not candidates:
            self._consume_password_timing(password)
            self._log("AUTH_IDENTIFIER_NOT_FOUND", request, started_at)
            return None
        if len(candidates) != 1:
            self._consume_password_timing(password)
            self._log("AUTH_IDENTIFIER_COLLISION", request, started_at)
            return None

        user = candidates[0]
        if not user.check_password(password):
            self._log("AUTH_BAD_PASSWORD", request, started_at)
            return None
        if not self.user_can_authenticate(user):
            self._log("AUTH_USER_INACTIVE", request, started_at)
            return None

        group_names = set(user.groups.values_list("name", flat=True))
        if not group_names.intersection(required_groups):
            self._log("AUTH_ROLE_DENIED", request, started_at)
            return None

        self._log("AUTH_SUCCESS", request, started_at)
        return user

    @staticmethod
    def _consume_password_timing(password: str) -> None:
        get_user_model()().set_password(password)

    @staticmethod
    def _log(code: str, request, started_at: float, *, exc_info: bool = False) -> None:
        correlation_id = getattr(request, "padesce_auth_correlation_id", "") if request else ""
        if not correlation_id:
            correlation_id = uuid.uuid4().hex
            if request is not None:
                request.padesce_auth_correlation_id = correlation_id
        duration_ms = round((time.monotonic() - started_at) * 1000)
        logger.info(
            "auth_event code=%s correlation_id=%s duration_ms=%s",
            code,
            correlation_id,
            duration_ms,
            exc_info=exc_info,
        )
