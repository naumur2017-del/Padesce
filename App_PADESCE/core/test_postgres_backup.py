from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from App_PADESCE.core import postgres_backup


class NativePostgresBackupTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def _settings(self):
        return override_settings(BASE_DIR=self.temp_dir.name)

    @patch("App_PADESCE.core.postgres_backup.subprocess.run")
    def test_pg_dump_failure_does_not_create_a_valid_backup(self, run):
        run.return_value.returncode = 1
        with self._settings(), patch.dict("os.environ", {"POSTGRES_DB": "isolated"}, clear=False):
            with self.assertRaises(postgres_backup.NativeBackupError):
                postgres_backup.create_native_backup()

    @patch("App_PADESCE.core.postgres_backup.subprocess.run")
    def test_empty_pg_dump_file_is_rejected(self, run):
        run.return_value.returncode = 0
        with self._settings(), patch.dict("os.environ", {"POSTGRES_DB": "isolated"}, clear=False):
            with self.assertRaises(postgres_backup.NativeBackupError):
                postgres_backup.create_native_backup()

    @patch("App_PADESCE.core.postgres_backup.subprocess.run")
    def test_backup_has_checksum(self, run):
        def write_dump(command, **kwargs):
            Path(command[command.index("--file") + 1]).write_bytes(b"postgres-dump")
            result = type("Result", (), {})()
            result.returncode = 0
            return result

        run.side_effect = write_dump
        with self._settings(), patch.dict("os.environ", {"POSTGRES_DB": "isolated"}, clear=False):
            result = postgres_backup.create_native_backup()
        self.assertEqual(len(str(result["checksum"])), 64)
        self.assertTrue(Path(result["path"]).with_suffix(".dump.sha256").exists())
