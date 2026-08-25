"""Forms used only when the feature-flagged operator backend is active."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from App_PADESCE.core.operator_auth import normalize_login_identifier


class OperatorLoginForm(AuthenticationForm):
    """Submit the canonical identifier while retaining Django's generic errors."""

    def clean_username(self):
        value = self.cleaned_data["username"]
        normalized = normalize_login_identifier(value)
        if not normalized:
            raise forms.ValidationError("Identifiant ou mot de passe incorrect.")
        return normalized
