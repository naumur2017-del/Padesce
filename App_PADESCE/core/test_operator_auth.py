import json
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import TestCase

from App_PADESCE.core.operator_auth import normalize_login_identifier


class NormalizeLoginIdentifierTests(TestCase):
    def test_normalizes_outer_and_invisible_whitespace_without_removing_accents(self):
        self.assertEqual(
            normalize_login_identifier("\u00a0 Op\u00e9ratrice\u200b  "),
            "op\u00e9ratrice",
        )

    def test_returns_empty_string_for_none_or_whitespace_only_values(self):
        self.assertEqual(normalize_login_identifier(None), "")
        self.assertEqual(normalize_login_identifier(" \t\n"), "")


class AuditOperatorAccountsCommandTests(TestCase):
    def test_reports_normalized_collisions_without_password_data(self):
        user_model = get_user_model()
        first = user_model.objects.create_user(username="Operatrice", password="safe-test-password")
        second = user_model.objects.create_user(username=" operatrice ", password="another-test-password")

        output = StringIO()
        call_command("audit_operator_accounts", format="json", stdout=output)

        report = json.loads(output.getvalue())
        self.assertEqual(report["summary"]["normalized_identifier_collisions"], 1)
        self.assertEqual(report["summary"]["users_in_normalized_collisions"], 2)
        self.assertNotIn(first.password, output.getvalue())
        self.assertNotIn(second.password, output.getvalue())

    def test_identifier_filter_is_normalized_and_does_not_modify_accounts(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="Operatrice", password="safe-test-password")
        initial_password = user.password

        output = StringIO()
        call_command(
            "audit_operator_accounts",
            format="json",
            identifier="  OPERATRICE\u200b ",
            dry_run=True,
            stdout=output,
        )

        report = json.loads(output.getvalue())
        self.assertEqual(report["filtered_user_count"], 1)
        user.refresh_from_db()
        self.assertEqual(user.password, initial_password)

    @patch("App_PADESCE.core.management.commands.audit_operator_accounts.get_user_model")
    def test_reports_a_clear_error_when_user_tables_are_unavailable(self, get_user_model_mock):
        user_model = Mock()
        user_model.USERNAME_FIELD = "username"
        user_model._default_manager.all.side_effect = OperationalError("no such table: auth_user")
        get_user_model_mock.return_value = user_model

        with self.assertRaisesMessage(CommandError, "tables utilisateurs sont indisponibles"):
            call_command("audit_operator_accounts", format="json")
