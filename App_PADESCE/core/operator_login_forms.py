"""Forms used only when the feature-flagged operator backend is active."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from App_PADESCE.core.operator_auth import normalize_login_identifier
from App_PADESCE.core.auth_throttling import OperatorLoginAttemptLimiter


class OperatorLoginForm(AuthenticationForm):
    """Submit the canonical identifier while retaining Django's generic errors."""

    def clean_username(self):
        value = self.cleaned_data["username"]
        normalized = normalize_login_identifier(value)
        if not normalized:
            raise forms.ValidationError("Identifiant ou mot de passe incorrect.")
        return normalized

    def clean(self):
        identifier = self.cleaned_data.get("username", "")
        limiter = OperatorLoginAttemptLimiter()
        if identifier and limiter.is_blocked(self.request, identifier):
            raise forms.ValidationError("Identifiant ou mot de passe incorrect.")

        try:
            cleaned_data = super().clean()
        except forms.ValidationError:
            if identifier:
                limiter.record_failure(self.request, identifier)
            raise

        if self.get_user() is not None:
            limiter.reset(self.request, identifier)
        return cleaned_data
