from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.media_integrity import audit_media_integrity


class MediaIntegrityTests(TestCase):
    def test_detects_orphans_without_deleting_them(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            orphan = Path(media_root) / "orphan.mp3"
            orphan.write_bytes(b"audio")
            report = audit_media_integrity()
            self.assertIn("orphan.mp3", report["orphan_files"])
            self.assertTrue(orphan.exists())
