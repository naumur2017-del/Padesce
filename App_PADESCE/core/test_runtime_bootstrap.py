from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from App_PADESCE.core import runtime_bootstrap


class RuntimeBootstrapTests(SimpleTestCase):
    def _marker_dir(self, base_dir: Path) -> Path:
        return runtime_bootstrap._runtime_marker_dir(base_dir)

    @patch("App_PADESCE.core.runtime_bootstrap.maybe_run_django_migrations")
    @patch("App_PADESCE.core.runtime_bootstrap.maybe_run_postgres_migration")
    @patch("App_PADESCE.core.runtime_bootstrap.load_runtime_env")
    def test_bootstrap_runtime_runs_all_steps(self, mock_load_env, mock_postgres, mock_migrate):
        base_dir = Path(tempfile.mkdtemp())

        runtime_bootstrap.bootstrap_runtime(base_dir)

        mock_load_env.assert_called_once_with(base_dir)
        mock_postgres.assert_called_once_with(base_dir)
        mock_migrate.assert_called_once_with(base_dir)

    @patch.dict("os.environ", {"NAUMUR_AUTO_MIGRATE_ON_BOOT": "1"}, clear=False)
    @patch("App_PADESCE.core.runtime_bootstrap._has_pending_django_migrations", return_value=False)
    @patch("django.core.management.call_command")
    def test_maybe_run_django_migrations_skips_when_up_to_date(self, mock_call_command, _mock_pending):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            migrated = runtime_bootstrap.maybe_run_django_migrations(base_dir)

            self.assertFalse(migrated)
            mock_call_command.assert_not_called()
            done_payload = json.loads(
                (self._marker_dir(base_dir) / runtime_bootstrap.AUTO_MIGRATE_DONE_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(done_payload["status"], "up_to_date")

    @patch.dict("os.environ", {"NAUMUR_AUTO_MIGRATE_ON_BOOT": "1"}, clear=False)
    @patch("App_PADESCE.core.runtime_bootstrap._has_pending_django_migrations", return_value=True)
    @patch("django.core.management.call_command")
    def test_maybe_run_django_migrations_applies_pending_migrations(self, mock_call_command, _mock_pending):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            migrated = runtime_bootstrap.maybe_run_django_migrations(base_dir)

            self.assertTrue(migrated)
            mock_call_command.assert_called_once_with("migrate", interactive=False, verbosity=0)
            done_payload = json.loads(
                (self._marker_dir(base_dir) / runtime_bootstrap.AUTO_MIGRATE_DONE_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(done_payload["status"], "migrated")

    @patch.dict("os.environ", {"NAUMUR_AUTO_MIGRATE_ON_BOOT": "1"}, clear=False)
    @patch("App_PADESCE.core.runtime_bootstrap._has_pending_django_migrations", return_value=True)
    @patch("django.core.management.call_command", side_effect=RuntimeError("boom"))
    def test_maybe_run_django_migrations_records_errors_without_raising(self, _mock_call_command, _mock_pending):
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            migrated = runtime_bootstrap.maybe_run_django_migrations(base_dir)

            self.assertFalse(migrated)
            error_text = (
                self._marker_dir(base_dir) / runtime_bootstrap.AUTO_MIGRATE_ERROR_FILENAME
            ).read_text(encoding="utf-8")
            self.assertIn("RuntimeError: boom", error_text)
