import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
        self.assertContains(page, "Modifier")
        self.assertContains(page, 'data-q2="OUI"')
        self.assertContains(page, 'data-declared="5"')
        self.assertContains(page, "<audio", html=False)
        self.assertContains(page, "fetch(form.dataset.submitUrl")
        self.assertNotContains(page, "fetch(form.action")

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

    def test_false_name_requires_and_saves_the_real_name(self):
        url = reverse("pas_forme_ii_save_form", args=[self.row.pk])
        incomplete = self.client.post(url, {"q2": "OUI", "nombre_seances_declare": "3", "faux_nom": "on"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(incomplete.status_code, 400)

        response = self.client.post(url, {"q2": "OUI", "nombre_seances_declare": "3", "faux_nom": "on", "vrai_nom": "Vrai Apprenant"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.row.refresh_from_db()
        self.assertTrue(self.row.faux_nom)
        self.assertEqual(self.row.vrai_nom, "Vrai Apprenant")

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

    def test_completed_form_can_only_be_modified_by_call_agent_or_admin(self):
        self.row.locked_by = self.user
        self.row.formulaire_rempli_at = timezone.now()
        self.row.status = "formulaire_rempli"
        self.row.save()
        other_user = get_user_model().objects.create_user(
            username="other-agent", password="test123"
        )
        url = reverse("pas_forme_ii_save_form", args=[self.row.pk])

        self.client.force_login(other_user)
        denied = self.client.post(
            url,
            {"q2": "OUI", "nombre_seances_declare": "2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(denied.status_code, 403)

        self.client.force_login(self.user)
        updated = self.client.post(
            url,
            {"q2": "NON", "nombre_seances_declare": "2"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(updated.status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.modified_by, self.user)
        self.assertIsNotNone(self.row.modified_at)
        self.assertEqual(self.row.locked_by, self.user)

        admin = get_user_model().objects.create_superuser(
            username="pfii-admin", password="test123", email="admin@example.com"
        )
        self.client.force_login(admin)
        updated_by_admin = self.client.post(
            url,
            {"q2": "OUI", "nombre_seances_declare": "4"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(updated_by_admin.status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.modified_by, admin)
        self.assertEqual(self.row.locked_by, self.user)

    def test_call_with_reminder_status_can_be_started(self):
        self.row.status = "a_rappeler"
        self.row.save(update_fields=["status", "updated_at"])

        response = self.client.post(
            reverse("pas_forme_ii_action", args=[self.row.pk]),
            {"action": "start"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "en_cours")
