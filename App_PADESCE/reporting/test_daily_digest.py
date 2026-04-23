from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.reporting import app_report


class DailyDigestEmailTests(TestCase):
    def _fake_report(self) -> dict:
        return {
            "generated_at": timezone.now(),
            "start_date": date(2026, 4, 23),
            "end_date": date(2026, 4, 23),
            "users": {"called_today": 5},
            "calls": {"completed": 12},
            "analysis": {
                "classes_count": 3,
                "prestations_count": 4,
                "prestataires_count": 2,
                "beneficiaires_count": 6,
            },
            "bugs": {"alarms_total": 1, "alarms_open": 0, "log_errors": 0},
            "best_hour": {"label": "10h00 - 10h59", "completed": 4},
            "user_call_rows": [],
        }

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST="smtp.example.com",
        DEFAULT_FROM_EMAIL="noreply@example.com",
        REPORT_EMAIL_TO="daily@example.com",
    )
    def test_send_daily_digest_email_attaches_padesce_and_cga_reports(self) -> None:
        def _write_padesce_report(output_path):
            path = Path(output_path)
            path.write_bytes(b"padesce-report")
            return {"path": str(path)}

        with (
            patch("App_PADESCE.reporting.app_report.build_application_report", return_value=self._fake_report()),
            patch("App_PADESCE.reporting.app_report.build_backup_status_summary", return_value={"status": "success", "label": "Succes", "detail": "Backup ok", "purged_backups": []}),
            patch("App_PADESCE.reporting.app_report.export_application_report_word", return_value=b"docx-report"),
            patch("App_PADESCE.reporting.app_report.build_padesce_calls_report", side_effect=_write_padesce_report),
            patch("App_PADESCE.reporting.app_report.build_cga_calls_report_workbook", return_value=b"cga-report"),
            patch("App_PADESCE.reporting.app_report._get_report_logo_path", return_value=None),
            patch.object(app_report, "HAS_DOCX", True),
        ):
            result = app_report.send_daily_digest_email(date(2026, 4, 23), date(2026, 4, 23))

        self.assertTrue(result["ok"])
        self.assertEqual(len(mail.outbox), 1)
        attachment_names = [attachment[0] for attachment in mail.outbox[0].attachments]
        self.assertTrue(any(name.startswith("rapport_application_") and name.endswith(".docx") for name in attachment_names))
        self.assertTrue(any(name.startswith("rapport_appels_padesce_") and name.endswith(".xlsx") for name in attachment_names))
        self.assertTrue(any(name.startswith("rapport_appels_cga_") and name.endswith(".xlsx") for name in attachment_names))


class DailyDigestTriggerViewTests(TestCase):
    @override_settings(REPORT_TRIGGER_TOKEN="report-secret")
    def test_daily_digest_trigger_accepts_anonymous_requests(self) -> None:
        with patch(
            "App_PADESCE.reporting.views.send_daily_digest_email",
            return_value={"ok": True, "detail": "Digest envoye"},
        ) as mock_send:
            response = self.client.post(
                reverse("reporting_daily_digest_trigger"),
                {"recipients": "daily@example.com"},
                HTTP_X_REPORT_TOKEN="report-secret",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        mock_send.assert_called_once()

    @override_settings(REPORT_TRIGGER_TOKEN="report-secret")
    def test_daily_digest_trigger_rejects_invalid_token(self) -> None:
        response = self.client.post(reverse("reporting_daily_digest_trigger"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "Token invalide ou manquant.")
