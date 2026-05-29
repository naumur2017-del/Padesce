from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from App_PADESCE.core import backup_manager, huggingface_sync


class BackupTriggerAutomationTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        backup_manager._jobs.clear()

    def test_backup_trigger_accepts_anonymous_requests(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_TRIGGER_TOKEN="secret-token"):
            with patch(
                "App_PADESCE.core.backup_manager.start_backup",
                return_value="job-123",
            ) as mock_start:
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
            sync_huggingface=False,
            require_huggingface=False,
        )

    def test_backup_trigger_can_require_huggingface_sync(self) -> None:
        with override_settings(BASE_DIR=self.temp_dir.name, BACKUP_TRIGGER_TOKEN="secret-token"):
            with patch(
                "App_PADESCE.core.backup_manager.start_backup",
                return_value="job-456",
            ) as mock_start:
                response = self.client.post(
                    reverse("backup_trigger"),
                    HTTP_X_BACKUP_TOKEN="secret-token",
                    HTTP_X_HUGGINGFACE_SYNC="1",
                    HTTP_X_HUGGINGFACE_REQUIRED="1",
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sync_huggingface"], True)
        self.assertEqual(response.json()["require_huggingface"], True)
        mock_start.assert_called_once_with(
            triggered_by="scheduled/github-actions",
            retention_days=30,
            sync_huggingface=True,
            require_huggingface=True,
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


class HuggingFaceBackupSyncTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

    def test_huggingface_sync_reports_missing_token_without_upload(self) -> None:
        db_path = self._create_sqlite_db("backup.sqlite3")
        initial = huggingface_sync.initial_status(enabled=True, required=True)

        with override_settings(
            HUGGINGFACE_TOKEN="",
            HF_TOKEN="",
            HUGGINGFACE_SPACE_REPO_ID="JackBrayan17/padesce-bot",
        ):
            status = huggingface_sync.sync_sqlite_backup_to_huggingface(
                db_path,
                backup_file=db_path.name,
                job_id="job-token",
                started_at="2026-05-29T17:00:00",
                triggered_by="test",
                tables_count=1,
                file_size=db_path.stat().st_size,
                status=initial,
            )

        self.assertEqual(status["status"], "error")
        self.assertIn("HUGGINGFACE_TOKEN", status["error"])

    def test_sqlite_backup_evaluation_checks_integrity(self) -> None:
        db_path = self._create_sqlite_db("valid.sqlite3")

        result = huggingface_sync.evaluate_sqlite_backup(db_path)

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"], "ok")
        self.assertEqual(result["tables_count"], 1)

    def _create_sqlite_db(self, name: str):
        db_path = Path(self.temp_dir.name) / name
        with closing(sqlite3.connect(db_path)) as conn:
            conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, label TEXT)")
            conn.execute("INSERT INTO sample (label) VALUES ('ok')")
            conn.commit()
        return db_path
