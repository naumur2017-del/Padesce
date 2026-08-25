import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase


class RepairOperatorAccountsCommandTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.retained = user_model.objects.create_superuser(
            username="retained-admin", password="safe-test-password"
        )
        self.demoted = user_model.objects.create_superuser(
            username="demoted-admin", password="safe-test-password"
        )

    def test_dry_run_reports_changes_without_writing(self):
        output = StringIO()

        call_command(
            "repair_operator_accounts",
            create_operator_group=True,
            retain_superuser_pk=self.retained.pk,
            format="json",
            stdout=output,
        )

        report = json.loads(output.getvalue())
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["superuser_pk_retained"], self.retained.pk)
        self.assertEqual(report["superuser_pks_to_demote"], [self.demoted.pk])
        self.assertFalse(Group.objects.filter(name="operatrice").exists())
        self.demoted.refresh_from_db()
        self.assertTrue(self.demoted.is_superuser)

    def test_apply_creates_group_and_demotes_only_selected_superusers(self):
        call_command(
            "repair_operator_accounts",
            create_operator_group=True,
            retain_superuser_pk=self.retained.pk,
            dry_run=False,
        )

        self.assertTrue(Group.objects.filter(name="operatrice").exists())
        self.retained.refresh_from_db()
        self.demoted.refresh_from_db()
        self.assertTrue(self.retained.is_superuser)
        self.assertFalse(self.demoted.is_superuser)

    def test_restore_requires_explicit_selected_primary_keys(self):
        self.demoted.is_superuser = False
        self.demoted.save(update_fields=["is_superuser"])

        call_command(
            "repair_operator_accounts",
            restore_superuser_pks=str(self.demoted.pk),
            dry_run=False,
        )

        self.demoted.refresh_from_db()
        self.assertTrue(self.demoted.is_superuser)

    def test_can_assign_all_currently_unassigned_accounts_to_operator_group(self):
        operator = get_user_model().objects.create_user(
            username="operator-without-group", password="safe-test-password"
        )
        output = StringIO()

        call_command(
            "repair_operator_accounts",
            create_operator_group=True,
            assign_all_users_without_groups=True,
            format="json",
            stdout=output,
        )

        report = json.loads(output.getvalue())
        self.assertIn(operator.pk, report["operator_user_pks_to_add"])
        self.assertFalse(operator.groups.exists())

        call_command(
            "repair_operator_accounts",
            create_operator_group=True,
            assign_all_users_without_groups=True,
            dry_run=False,
        )

        operator.refresh_from_db()
        self.assertTrue(operator.groups.filter(name="operatrice").exists())
