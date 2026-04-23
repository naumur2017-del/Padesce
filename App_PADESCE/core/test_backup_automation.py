from __future__ import annotations

from datetime import datetime, timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from App_PADESCE.core import backup_manager


class BackupTriggerAutomationTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        backup_manager._jobs.clear()

    def test_backup_trigger_accepts_anonymous_requests(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_TRIGGER_TOKEN="secret-token"):
            with patch("App_PADESCE.core.backup_manager.start_backup", return_value="job-123") as mock_start:
                response = self.client.post(
                    reverse("backup_trigger"),
                    HTTP_X_BACKUP_TOKEN="secret-token",
                    HTTP_X_BACKUP_RETENTION_DAYS="7",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-123")
        self.assertEqual(response.json()["retention_days"], 14)
        mock_start.assert_called_once_with(
            triggered_by="scheduled/github-actions",
            retention_days=14,
        )

    def test_backup_trigger_rejects_invalid_token_without_redirect(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_TRIGGER_TOKEN="secret-token"):
            response = self.client.post(reverse("backup_trigger"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Token invalide ou manquant.")
        self.assertFalse(response.has_header("Location"))

    def test_backup_trigger_status_reads_history_without_redirect(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_TRIGGER_TOKEN="secret-token"):
            backup_manager._save_history(
                [
                    {
                        "id": "job-history",
                        "status": "success",
                        "backup_file": "backup_20260423_170000.sqlite3",
                    }
                ]
            )
            response = self.client.get(
                reverse("backup_trigger_status", args=["job-history"]),
                HTTP_X_BACKUP_TOKEN="secret-token",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        self.assertFalse(response.has_header("Location"))


class BackupRetentionTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        backup_manager._jobs.clear()

    def test_resolve_backup_retention_days_is_clamped_between_14_and_30(self) -> None:
        self.assertEqual(backup_manager.resolve_backup_retention_days("2"), 14)
        self.assertEqual(backup_manager.resolve_backup_retention_days("21"), 21)
        self.assertEqual(backup_manager.resolve_backup_retention_days("999"), 30)

    def test_purge_old_backups_deletes_expired_files_and_cleans_history(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_RETENTION_DAYS="30"):
            backup_dir = backup_manager._backup_dir()
            old_name = f"backup_{(datetime.now() - timedelta(days=45)):%Y%m%d_%H%M%S}.sqlite3"
            recent_name = f"backup_{(datetime.now() - timedelta(days=5)):%Y%m%d_%H%M%S}.sqlite3"

            (backup_dir / old_name).write_text("old-backup", encoding="utf-8")
            (backup_dir / recent_name).write_text("recent-backup", encoding="utf-8")
            backup_manager._save_history(
                [
                    {"id": "recent", "backup_file": recent_name, "status": "success"},
                    {"id": "old", "backup_file": old_name, "status": "success"},
                ]
            )

            result = backup_manager.purge_old_backups(retention_days=30)
            history = backup_manager.load_history()

        self.assertIn(old_name, result["deleted_files"])
        self.assertFalse((backup_dir / old_name).exists())
        self.assertTrue((backup_dir / recent_name).exists())
        self.assertEqual([entry["id"] for entry in history], ["recent"])
