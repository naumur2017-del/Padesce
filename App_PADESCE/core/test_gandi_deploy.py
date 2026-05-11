from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from App_PADESCE.core.deployment_live import LIVE_MARKER_FILENAME
from App_PADESCE.core.gandi_deploy import (
    _app_env_values_from_env,
    _cache_busted_url,
    _http_check_with_retries,
    _merge_env_content,
    build_local_manifest,
    compute_diff,
    deployment_config_summary,
    local_manifest_entry,
    save_runtime_config,
)


class _DummyState:
    def update_step(self, key: str, *, message: str = "", progress: int | None = None) -> None:
        self.last_update = (key, message, progress)


class GandiDeployHelpersTests(SimpleTestCase):
    @override_settings(BASE_DIR="C:/tmp")
    def test_compute_diff_keeps_remote_only_files_untracked_without_manifest(self) -> None:
        with patch("App_PADESCE.core.gandi_deploy.remote_file_sha256", return_value="same-hash"):
            additions, modifications, deletions, remote_untracked = compute_diff(
                local_manifest={
                    "App_PADESCE/example.py": {"size": 10, "sha256": "same-hash"},
                },
                remote_manifest=None,
                remote_scan={
                    "App_PADESCE/example.py": {"size": 10, "mtime": 1},
                    "legacy/old.txt": {"size": 4, "mtime": 1},
                },
                remote_root="/vhosts/default",
                sftp=object(),
                state=_DummyState(),
            )

        self.assertEqual(additions, [])
        self.assertEqual(modifications, [])
        self.assertEqual(deletions, [])
        self.assertEqual(remote_untracked, ["legacy/old.txt"])

    def test_build_local_manifest_skips_sensitive_and_runtime_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "App_PADESCE").mkdir()
            (root / "logs").mkdir()
            (root / "media").mkdir()
            (root / "App_PADESCE" / "keep.py").write_text("print('ok')", encoding="utf-8")
            (root / ".env").write_text("SECRET=1", encoding="utf-8")
            (root / "db.sqlite3").write_text("db", encoding="utf-8")
            (root / LIVE_MARKER_FILENAME).write_text("{}", encoding="utf-8")
            (root / "logs" / "app.log").write_text("ignored", encoding="utf-8")
            (root / "media" / "avatar.png").write_text("ignored", encoding="utf-8")

            manifest = build_local_manifest(root)

        self.assertEqual(sorted(manifest), ["App_PADESCE/keep.py"])

    def test_build_local_manifest_can_include_collected_staticfiles_when_requested(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "staticfiles" / "branding").mkdir(parents=True)
            (root / "staticfiles" / "branding" / "logo.png").write_text(
                "logo",
                encoding="utf-8",
            )

            manifest = build_local_manifest(root, include_paths=("staticfiles",))

        self.assertEqual(sorted(manifest), ["staticfiles/branding/logo.png"])

    def test_runtime_config_fills_missing_username_and_token(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "App_PADESCE").mkdir()
            with override_settings(BASE_DIR=temp_dir):
                with patch.dict(
                    os.environ,
                    {
                        "GANDI_SFTP_HOST": "",
                        "GANDI_SFTP_PORT": "",
                        "GANDI_SFTP_DOMAIN": "",
                        "GANDI_SFTP_USERNAME": "",
                        "GANDI_SFTP_TOKEN": "",
                        "GANDI_DEPLOY_VERIFY_URL": "",
                        "GANDI_DEPLOY_LOCAL_ROOT": temp_dir,
                    },
                    clear=False,
                ):
                    save_runtime_config(
                        {
                            "GANDI_SFTP_HOST": "sftp.sd3.gpaas.net",
                            "GANDI_SFTP_PORT": "22",
                            "GANDI_SFTP_DOMAIN": "call.naumur.com",
                            "GANDI_SFTP_USERNAME": "1fc95212-285b-11f1-aa03-00163e94b645",
                            "GANDI_SFTP_TOKEN": "token-123",
                            "GANDI_DEPLOY_VERIFY_URL": "https://call.naumur.com",
                            "GANDI_DEPLOY_LOCAL_ROOT": temp_dir,
                        }
                    )
                    summary = deployment_config_summary()

        self.assertTrue(summary["ready"])
        self.assertTrue(summary["token_present"])
        self.assertEqual(summary["host"], "sftp.sd3.gpaas.net")

    def test_local_manifest_entry_reflects_latest_file_content(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "App_PADESCE").mkdir()
            target = root / "App_PADESCE" / "latest.py"
            target.write_text("print('v1')\n", encoding="utf-8")
            first_entry = local_manifest_entry(root, "App_PADESCE/latest.py")
            target.write_text("print('v2')\n", encoding="utf-8")
            second_entry = local_manifest_entry(root, "App_PADESCE/latest.py")

        self.assertIsNotNone(first_entry)
        self.assertIsNotNone(second_entry)
        self.assertNotEqual(first_entry["sha256"], second_entry["sha256"])

    def test_merge_env_content_updates_target_keys_without_erasing_other_lines(self) -> None:
        existing = (
            "DJANGO_SECRET_KEY=abc123\n"
            "MICROSOFT_GRAPH_CLIENT_ID=old-client\n"
            "# keep comment\n"
            "EMAIL_HOST=smtp.gmail.com\n"
        )
        merged = _merge_env_content(
            existing,
            {
                "MICROSOFT_GRAPH_CLIENT_ID": "new-client",
                "MICROSOFT_GRAPH_TENANT_ID": "tenant-001",
            },
        )

        self.assertIn("DJANGO_SECRET_KEY=abc123", merged)
        self.assertIn("MICROSOFT_GRAPH_CLIENT_ID=new-client", merged)
        self.assertIn("MICROSOFT_GRAPH_TENANT_ID=tenant-001", merged)
        self.assertIn("# keep comment", merged)
        self.assertIn("EMAIL_HOST=smtp.gmail.com", merged)

    def test_app_env_values_uses_export_key_as_cga_public_key_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXPORT_API_KEY": "export-secret",
                "CGA_PUBLIC_API_KEY": "",
            },
            clear=False,
        ):
            values = _app_env_values_from_env()

        self.assertEqual(values["EXPORT_API_KEY"], "export-secret")
        self.assertEqual(values["CGA_PUBLIC_API_KEY"], "export-secret")

    def test_app_env_values_prefers_explicit_cga_public_key(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EXPORT_API_KEY": "export-secret",
                "CGA_PUBLIC_API_KEY": "cga-secret",
            },
            clear=False,
        ):
            values = _app_env_values_from_env()

        self.assertEqual(values["CGA_PUBLIC_API_KEY"], "cga-secret")

    def test_cache_busted_url_preserves_existing_query(self) -> None:
        url = _cache_busted_url(
            "https://call.naumur.com/deploiement/live/?format=json",
            run_id="run-123",
            attempt=2,
        )

        self.assertTrue(url.startswith("https://call.naumur.com/deploiement/live/?"))
        self.assertIn("format=json", url)
        self.assertIn("_deploy_run=run-123", url)
        self.assertIn("_deploy_attempt=2", url)

    def test_http_check_with_retries_allows_transient_public_failure(self) -> None:
        with (
            patch(
                "App_PADESCE.core.gandi_deploy._http_check",
                side_effect=[
                    {"ok": False, "message": "timeout"},
                    {"ok": True, "status_code": 200, "final_url": "https://call.naumur.com/"},
                ],
            ) as check_mock,
            patch("App_PADESCE.core.gandi_deploy.time.sleep") as sleep_mock,
        ):
            result = _http_check_with_retries(
                "https://call.naumur.com",
                attempts=2,
                delay_seconds=0,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(check_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0)


class DeploymentViewsTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.superuser = user_model.objects.create_user(
            username="deploy-admin",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )

    @patch(
        "App_PADESCE.core.deployment_views._start_pipeline",
        return_value=("run-123", SimpleNamespace(pid=9876)),
    )
    @patch("App_PADESCE.core.deployment_views.get_active_run", return_value=None)
    def test_superadmin_can_start_preview_pipeline(self, active_mock, start_mock) -> None:
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("deployment_start"), {"mode": "preview"}, HTTP_ACCEPT="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_id"], "run-123")
        start_mock.assert_called_once_with("preview")

    @patch(
        "App_PADESCE.core.deployment_views.get_active_run",
        return_value={"id": "running-1", "status": "running"},
    )
    def test_start_returns_conflict_when_run_is_already_active(self, active_mock) -> None:
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("deployment_start"), {"mode": "deploy"}, HTTP_ACCEPT="application/json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["run_id"], "running-1")

    @patch("App_PADESCE.core.deployment_views.save_runtime_config")
    @patch(
        "App_PADESCE.core.deployment_views.deployment_config_summary", return_value={"ready": True}
    )
    def test_superadmin_can_save_runtime_config(self, summary_mock, save_mock) -> None:
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse("deployment_config_save"),
            {
                "host": "sftp.sd3.gpaas.net",
                "username": "1fc95212-285b-11f1-aa03-00163e94b645",
                "token": "token-123",
            },
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        save_mock.assert_called_once()

    @patch(
        "App_PADESCE.core.deployment_views.load_report",
        return_value={"id": "archived-run", "status": "completed"},
    )
    @patch("App_PADESCE.core.deployment_views.load_run_state", return_value=None)
    def test_status_falls_back_to_archived_report(self, run_mock, report_mock) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("deployment_status", args=["archived-run"]), HTTP_ACCEPT="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["run"]["id"], "archived-run")

    @patch(
        "App_PADESCE.core.deployment_views.load_history_entry",
        return_value={
            "id": "history-only-run",
            "mode": "deploy",
            "status": "failed",
            "started_at": "2026-03-31T08:00:00+00:00",
            "completed_at": "2026-03-31T08:05:00+00:00",
            "summary": {"remote_path": "/vhosts/default"},
            "error": "Ancien resume",
            "live_refresh": {"reloaded": False, "required": True, "message": "Controle archive"},
        },
    )
    @patch("App_PADESCE.core.deployment_views.load_report", return_value=None)
    @patch("App_PADESCE.core.deployment_views.load_run_state", return_value=None)
    def test_status_falls_back_to_history_summary_when_report_file_is_missing(
        self, run_mock, report_mock, history_mock
    ) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("deployment_status", args=["history-only-run"]), HTTP_ACCEPT="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["run"]["archived"])
        self.assertEqual(response.json()["run"]["id"], "history-only-run")

    @patch("App_PADESCE.core.deployment_views.load_history_entry", return_value=None)
    @patch("App_PADESCE.core.deployment_views.load_report", return_value=None)
    @patch("App_PADESCE.core.deployment_views.load_run_state", return_value=None)
    def test_status_returns_placeholder_archive_instead_of_404_when_everything_is_missing(
        self, run_mock, report_mock, history_mock
    ) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("deployment_status", args=["missing-run"]), HTTP_ACCEPT="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertTrue(response.json()["run"]["archived"])
        self.assertEqual(response.json()["run"]["id"], "missing-run")

    def test_live_status_endpoint_is_public_and_returns_marker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / LIVE_MARKER_FILENAME).write_text('{"run_id": "run-live"}', encoding="utf-8")
            with override_settings(BASE_DIR=temp_dir):
                response = self.client.get(
                    reverse("deployment_live_status"), HTTP_ACCEPT="application/json"
                )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["marker"]["run_id"], "run-live")
