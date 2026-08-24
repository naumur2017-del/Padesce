from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class DiagnoseOperatorLoginTests(TestCase):
    def test_strips_identifier_and_never_outputs_password_hash(self):
        user = get_user_model().objects.create_user(username="operatrice", password="secret-pass")
        output = StringIO()
        call_command("diagnose_operator_login", identifier=" operatrice ", stdout=output)
        text = output.getvalue()
        self.assertIn("comptes_correspondants: 1", text)
        self.assertIn("espaces_avant_ou_apres", text)
        self.assertNotIn(user.password, text)
