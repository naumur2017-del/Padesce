import io
import tempfile

import openpyxl

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

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
