import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from App_PADESCE.appels.models import AppelPasFormeII


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="padesce-pas-forme-ii-tests-"),
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class AppelPasFormeIISaveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="pas-forme-ii-agent",
            password="test123",
        )
        self.client.force_login(self.user)
        self.row = AppelPasFormeII.objects.create(
            reference_code="PFII-001",
            prestation_id="PRESTA-001",
            nom="Apprenant Test",
            telephone="690000001",
            beneficiaire="Structure Test",
            prestataire="Prestataire Test",
            total_presence=4,
            total_seances=6,
            nombre_seances_source=4,
        )

    def test_completed_form_is_saved_counted_and_exposes_audio(self):
        response = self.client.post(
            reverse("pas_forme_ii_save_form", args=[self.row.pk]),
            {
                "action": "terminer",
                "q2": "OUI",
                "nombre_seances_declare": "5",
                "audio": SimpleUploadedFile(
                    "appel.webm",
                    b"test-audio-content",
                    content_type="audio/webm",
                ),
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.row.refresh_from_db()
        self.assertEqual(self.row.membre_structure, "OUI")
        self.assertEqual(self.row.nombre_seances_declare, 5)
        self.assertEqual(self.row.status, "formulaire_avec_audio")
        self.assertIsNotNone(self.row.formulaire_rempli_at)
        self.assertTrue(self.row.audio_file.name)

        page = self.client.get(reverse("pas_forme_ii_index"))
        self.assertEqual(page.context["thresholds"][0]["completed"], 1)
        self.assertNotContains(page, 'class="btn open"')
        self.assertContains(page, "Consulter la ligne")
        self.assertContains(page, 'data-q2="OUI"')
        self.assertContains(page, 'data-declared="5"')
        self.assertContains(page, "<audio", html=False)

    def test_invalid_form_is_rejected_without_being_counted(self):
        response = self.client.post(
            reverse("pas_forme_ii_save_form", args=[self.row.pk]),
            {"action": "terminer", "q2": "", "nombre_seances_declare": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.row.refresh_from_db()
        self.assertIsNone(self.row.formulaire_rempli_at)
        self.assertEqual(self.row.status, "en_attente")

    def test_start_action_is_persisted_for_ajax(self):
        response = self.client.post(
            reverse("pas_forme_ii_action", args=[self.row.pk]),
            {"action": "start"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "en_cours")
        self.assertEqual(self.row.locked_by, self.user)
