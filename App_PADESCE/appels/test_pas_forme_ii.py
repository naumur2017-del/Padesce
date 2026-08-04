import io
import tempfile

import openpyxl

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import AppelPasFormeII


def _import_file(rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Feuil1"
    sheet.append(
        [
            "PRESTATION ID",
            "APPRENANTS",
            "NUMERO",
            "BENEFICIAIRES",
            "PRESTATAIRES",
            "GENRE",
            "FENETRE",
            "ABSENT DANS CONSOLIDE",
            "TOTAL PRESENCE",
            "TOTAL SEANCE",
            "SEUIL 75%",
            "NOMBRE SEANCE",
            "FORME FINAL",
        ]
    )
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return SimpleUploadedFile(
        "pas-formes-ii.xlsx",
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(prefix="padesce-pas-forme-ii-import-tests-"),
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class AppelPasFormeIIImportTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="pas-forme-ii-admin",
            password="test123",
            email="admin@example.com",
        )
        self.client.force_login(self.admin)

    def test_comparison_keeps_matches_deactivates_missing_and_adds_new_rows(self):
        matching = AppelPasFormeII.objects.create(
            reference_code="PRESTA-001-690000001-apprenant-conserve",
            prestation_id="PRESTA-001",
            nom="Apprenant Conserve",
            telephone="690000001",
            genre="Genre plateforme",
            commentaire="Historique à préserver",
            status="formulaire_rempli",
        )
        matching_updated_at = matching.updated_at
        missing = AppelPasFormeII.objects.create(
            reference_code="PRESTA-002-690000002-apprenant-absent",
            prestation_id="PRESTA-002",
            nom="Apprenant Absent",
            telephone="690000002",
            commentaire="Données conservées en base",
        )

        response = self.client.post(
            reverse("pas_forme_ii_index"),
            {
                "import_action": "compare_sync",
                "file": _import_file(
                    [
                        [
                            "PRESTA-001", "Apprenant Conserve", "690000001",
                            "B1", "P1", "Genre fichier", "F1", "NON",
                            4, 6, 5, 4, "OUI",
                        ],
                        [
                            "PRESTA-003", "Nouvel Apprenant", "690000003",
                            "B3", "P3", "F", "F2", "NON",
                            5, 7, 6, 5, "NON",
                        ],
                    ]
                ),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        matching.refresh_from_db()
        missing.refresh_from_db()
        self.assertTrue(matching.is_active)
        self.assertEqual(matching.genre, "Genre plateforme")
        self.assertEqual(matching.commentaire, "Historique à préserver")
        self.assertEqual(matching.status, "formulaire_rempli")
        self.assertEqual(matching.updated_at, matching_updated_at)
        self.assertFalse(missing.is_active)
        self.assertEqual(missing.commentaire, "Données conservées en base")

        new_row = AppelPasFormeII.objects.get(
            reference_code="PRESTA-003-690000003-nouvel-apprenant"
        )
        self.assertTrue(new_row.is_active)
        self.assertEqual(new_row.beneficiaire, "B3")
        self.assertEqual(new_row.prestataire, "P3")
        self.assertEqual(new_row.genre, "F")
        self.assertEqual(new_row.fenetre, "F2")
        self.assertFalse(new_row.absent_dans_consolide)
        self.assertEqual(new_row.total_presence, 5)
        self.assertContains(response, "1 inchangés")
        self.assertContains(response, "1 désactivés")
        self.assertContains(response, "1 ajoutés")
        self.assertContains(response, "Comparer et mettre à jour")

    def test_comparison_reactivates_a_row_without_losing_its_history(self):
        inactive = AppelPasFormeII.objects.create(
            reference_code="PRESTA-004-690000004-apprenant-retour",
            prestation_id="PRESTA-004",
            nom="Apprenant Retour",
            telephone="690000004",
            is_active=False,
            commentaire="Ancien compte rendu",
            genre="Ancien genre",
        )

        self.client.post(
            reverse("pas_forme_ii_index"),
            {
                "import_action": "compare_sync",
                "file": _import_file(
                    [
                        [
                            "PRESTA-004", "Apprenant Retour", "690000004",
                            "B4", "P4", "M", "F3", "OUI",
                            2, 4, 3, 2, "NON",
                        ]
                    ]
                ),
            },
        )

        inactive.refresh_from_db()
        self.assertTrue(inactive.is_active)
        self.assertEqual(inactive.commentaire, "Ancien compte rendu")
        self.assertEqual(inactive.genre, "M")
        self.assertEqual(inactive.fenetre, "F3")
        self.assertTrue(inactive.absent_dans_consolide)

    def test_empty_comparison_file_does_not_deactivate_existing_rows(self):
        existing = AppelPasFormeII.objects.create(
            reference_code="PRESTA-005-690000005-apprenant-protege",
            prestation_id="PRESTA-005",
            nom="Apprenant Protege",
            telephone="690000005",
        )

        response = self.client.post(
            reverse("pas_forme_ii_index"),
            {"import_action": "compare_sync", "file": _import_file([])},
            follow=True,
        )

        existing.refresh_from_db()
        self.assertTrue(existing.is_active)
        self.assertContains(response, "Comparaison annulée")

    def test_page_uses_ten_percent_threshold_with_ceiling(self):
        calls = []
        for prestation_id, total in (("PRESTA-TEN", 10), ("PRESTA-ELEVEN", 11)):
            for index in range(total):
                calls.append(
                    AppelPasFormeII(
                        reference_code=f"{prestation_id}-{index}",
                        prestation_id=prestation_id,
                        nom=f"Apprenant {prestation_id} {index}",
                        formulaire_rempli_at=timezone.now() if index == 0 else None,
                    )
                )
        AppelPasFormeII.objects.bulk_create(calls)

        response = self.client.get(reverse("pas_forme_ii_index"))
        thresholds = {row["prestation_id"]: row for row in response.context["thresholds"]}

        self.assertEqual(response.context["pas_forme_ii_threshold_percent"], 10)
        self.assertEqual(thresholds["PRESTA-TEN"]["target"], 1)
        self.assertEqual(thresholds["PRESTA-ELEVEN"]["target"], 2)
        self.assertTrue(thresholds["PRESTA-TEN"]["reached"])
        self.assertFalse(thresholds["PRESTA-ELEVEN"]["reached"])
        self.assertContains(response, "Seuil de formulaires remplis par prestation — 10 %")


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

    def _reach_prestation_threshold(self, *, completed=1):
        rows = []
        for index in range(9):
            rows.append(
                AppelPasFormeII(
                    reference_code=f"PFII-QUOTA-{index}",
                    prestation_id=self.row.prestation_id,
                    nom=f"Apprenant quota {index}",
                    telephone=f"6900001{index:02d}",
                    formulaire_rempli_at=timezone.now() if index < completed else None,
                )
            )
        AppelPasFormeII.objects.bulk_create(rows)

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

    def test_threshold_reached_hides_every_new_contact_action(self):
        self._reach_prestation_threshold()

        page = self.client.get(reverse("pas_forme_ii_index"))

        self.assertNotContains(page, 'class="btn open"')
        self.assertContains(page, "Quota 10 % atteint — contact bloqué")
        self.assertContains(page, "Bloqués")

    def test_threshold_reached_blocks_start_resume_and_success_on_backend(self):
        self._reach_prestation_threshold(completed=2)
        url = reverse("pas_forme_ii_action", args=[self.row.pk])

        for action_name in ("start", "resume", "reussi"):
            with self.subTest(action=action_name):
                response = self.client.post(
                    url,
                    {"action": action_name},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(response.status_code, 409)
                self.assertFalse(response.json()["ok"])
                self.assertTrue(response.json()["threshold_reached"])

        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "en_attente")
        self.assertIsNone(self.row.locked_by)

    def test_threshold_reached_blocks_recall_and_form_submission_on_backend(self):
        self._reach_prestation_threshold()
        url = reverse("pas_forme_ii_save_form", args=[self.row.pk])

        for payload in (
            {"action": "rappeler", "rappel_at": "2026-08-05T10:00"},
            {"action": "terminer", "q2": "OUI", "nombre_seances_declare": "4"},
        ):
            with self.subTest(action=payload["action"]):
                response = self.client.post(
                    url,
                    payload,
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(response.status_code, 409)
                self.assertFalse(response.json()["ok"])
                self.assertTrue(response.json()["threshold_reached"])

        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "en_attente")
        self.assertIsNone(self.row.formulaire_rempli_at)
        self.assertIsNone(self.row.rappel_at)

    def test_pause_remains_available_to_stop_an_in_progress_call_at_threshold(self):
        self._reach_prestation_threshold()
        self.row.status = "en_cours"
        self.row.locked_by = self.user
        self.row.save(update_fields=["status", "locked_by", "updated_at"])

        response = self.client.post(
            reverse("pas_forme_ii_action", args=[self.row.pk]),
            {"action": "pause"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "pause")
