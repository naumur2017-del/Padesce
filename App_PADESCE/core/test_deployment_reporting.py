from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from django.core import mail
from django.test import SimpleTestCase, override_settings

from App_PADESCE.core.deployment_reporting import record_and_notify_deployment


class DeploymentReportingTests(SimpleTestCase):
    @override_settings(
        DEPLOYMENT_EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEPLOYMENT_REPORT_EMAIL_TO="jackbrayan1707@gmail.com",
        DEFAULT_FROM_EMAIL="naumur2017@gmail.com",
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_USE_TLS=True,
        EMAIL_HOST_USER="naumur2017@gmail.com",
        EMAIL_HOST_PASSWORD="secret",
    )
    def test_record_and_notify_deployment_writes_reports_and_sends_email(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with override_settings(BASE_DIR=temp_dir):
                result = record_and_notify_deployment(
                    {
                        "id": "run-001",
                        "mode": "deploy",
                        "status": "completed",
                        "started_at": "2026-03-30T19:00:00+00:00",
                        "completed_at": "2026-03-30T19:05:00+00:00",
                        "progress_pct": 100,
                        "error": "",
                        "config": {"ready": True},
                        "summary": {
                            "additions": 2,
                            "modifications": 1,
                            "deletions": 0,
                            "remote_untracked": 4,
                            "remote_path": "/vhosts/default",
                        },
                        "verification": {
                            "remote_manifest": True,
                            "http_check": {"status_code": 200, "ok": True},
                            "errors": [],
                        },
                        "steps": [
                            {
                                "label": "Preparation",
                                "status": "completed",
                                "message": "OK",
                                "started_at": "",
                                "completed_at": "",
                            },
                        ],
                        "diff": {
                            "additions": ["a.py", "b.py"],
                            "modifications": ["c.py"],
                            "deletions": [],
                            "remote_untracked": ["legacy.txt"],
                        },
                        "logs": [
                            {
                                "at": "2026-03-30T19:00:00+00:00",
                                "level": "info",
                                "message": "Pipeline termine.",
                            },
                        ],
                    }
                )

                self.assertTrue(result["email"]["sent"])
                self.assertTrue(mail.outbox)
                self.assertIn("run-001", mail.outbox[0].subject)
                self.assertTrue(mail.outbox[0].alternatives)
                self.assertGreaterEqual(len(mail.outbox[0].attachments), 4)

                report_json = json.loads(open(result["json_path"], encoding="utf-8").read())
                self.assertEqual(report_json["id"], "run-001")
                self.assertTrue(open(result["markdown_path"], encoding="utf-8").read())
                self.assertTrue(result["xlsx_path"])
                self.assertTrue(open(result["xlsx_path"], "rb").read(4))
                self.assertTrue(result["history_xlsx_path"])
                self.assertTrue(open(result["history_xlsx_path"], "rb").read(4))
                history = json.loads(open(result["history_path"], encoding="utf-8").read())
                self.assertEqual(history[0]["id"], "run-001")
