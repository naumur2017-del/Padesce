from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from App_PADESCE.appels.consolidation_views import (
    _build_filter_options,
    _create_appels_from_candidates,
    _filtered_candidates,
    consolidation_pending_appels,
)
from App_PADESCE.appels.models import Appel, AppelAnswers, AppelImportArchive


class ConsolidationFilterTests(SimpleTestCase):
    def test_filter_options_only_expose_related_values(self):
        candidates = [
            {
                "code": "AB0E",
                "nom": "Fanta Adamou",
                "classe_label": "CLA001",
                "prestataire": "Prestataire A",
                "beneficiaire": "Beneficiaire A",
                "formation_padesce": "Formation A",
                "cohorte": "1",
                "fenetre": "2",
                "statut_prestation": "TERMINE",
            },
            {
                "code": "AB0F",
                "nom": "Hadjaratou Abbou",
                "classe_label": "CLA001",
                "prestataire": "Prestataire A",
                "beneficiaire": "Beneficiaire A",
                "formation_padesce": "Formation A",
                "cohorte": "1",
                "fenetre": "2",
                "statut_prestation": "TERMINE",
            },
            {
                "code": "XY10",
                "nom": "Autre Nom",
                "classe_label": "CLA002",
                "prestataire": "Prestataire B",
                "beneficiaire": "Beneficiaire B",
                "formation_padesce": "Formation B",
                "cohorte": "3",
                "fenetre": "3",
                "statut_prestation": "ARRETE",
            },
        ]
        filters = {
            "q": "",
            "classe": "CLA001",
            "prestataire": "",
            "beneficiaire": "",
            "formation": "",
            "cohorte": "",
            "fenetre": "",
            "statut_prestation": "TERMINE",
        }

        filtered = _filtered_candidates(candidates, filters)
        options = _build_filter_options(candidates, filters)

        self.assertEqual(len(filtered), 2)
        self.assertEqual([item["value"] for item in options["prestataire"]], ["Prestataire A"])
        self.assertEqual([item["value"] for item in options["beneficiaire"]], ["Beneficiaire A"])
        self.assertEqual([item["value"] for item in options["cohorte"]], ["1"])


class ConsolidationImportTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username="admin",
            password="test123",
            is_staff=True,
            is_superuser=True,
        )

    def test_create_appels_from_candidates_skips_existing_codes(self):
        Appel.objects.create(code="AB0E", nom="Deja present")

        created, skipped = _create_appels_from_candidates(
            [
                {
                    "code": "AB0E",
                    "nom": "Fanta Adamou",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "lieu": "Mindif",
                    "classe_label": "CLA001",
                    "fenetre": "3",
                    "telephone1": "694666763",
                    "telephone2": "",
                    "type_formation_declaree": "Transformation",
                    "formation_padesce": "Transformation des produits laitiers",
                },
                {
                    "code": "NEW1",
                    "nom": "Nouvel Apprenant",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "lieu": "Mindif",
                    "classe_label": "CLA001",
                    "fenetre": "3",
                    "telephone1": "699999999",
                    "telephone2": "",
                    "type_formation_declaree": "Transformation",
                    "formation_padesce": "Transformation des produits laitiers",
                },
            ]
        )

        self.assertEqual(created, 1)
        self.assertEqual(skipped, 1)
        self.assertTrue(Appel.objects.filter(code="NEW1").exists())
        self.assertEqual(AppelImportArchive.objects.filter(source_code="NEW1").count(), 1)

    @patch("App_PADESCE.appels.consolidation_views.messages.success")
    @patch("App_PADESCE.appels.consolidation_views.build_consolidation_call_candidates")
    def test_consolidation_pending_appels_batch_action_uses_current_filter(self, mock_build_candidates, mock_messages_success):
        mock_build_candidates.return_value = {
            "source": {"name": "fichier consolide.xlsm", "modified_label": "24/03/2026 a 12:00"},
            "sheet_name": "Consolidation",
            "count": 2,
            "source_rows": 2,
            "duplicate_codes": [],
            "records": [
                {
                    "code": "CLA001A",
                    "nom": "Alpha",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "formation_padesce": "Formation A",
                    "type_formation_declaree": "Formation A",
                    "classe_label": "CLA001",
                    "fenetre": "2",
                    "cohorte": "1",
                    "telephone1": "690000001",
                    "telephone2": "",
                    "lieu": "Lieu A",
                    "statut_prestation": "TERMINE",
                },
                {
                    "code": "CLA002A",
                    "nom": "Beta",
                    "prestataire": "Prestataire B",
                    "beneficiaire": "Beneficiaire B",
                    "formation_padesce": "Formation B",
                    "type_formation_declaree": "Formation B",
                    "classe_label": "CLA002",
                    "fenetre": "3",
                    "cohorte": "2",
                    "telephone1": "690000002",
                    "telephone2": "",
                    "lieu": "Lieu B",
                    "statut_prestation": "TERMINE",
                },
            ],
        }

        request = self.factory.post(
            "/appels/consolidation/a-charger/",
            data={
                "action": "create_batch",
                "batch_size": "1",
                "return_query": "classe=CLA001&statut_prestation=TERMINE",
            },
        )
        request.user = self.user

        response = consolidation_pending_appels(request)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Appel.objects.filter(code="CLA001A").exists())
        self.assertFalse(Appel.objects.filter(code="CLA002A").exists())
        self.assertTrue(mock_messages_success.called)


class AppelsIndexFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="appels-viewer",
            password="test123",
        )
        self.modifier = get_user_model().objects.create_user(
            username="answer-editor",
            password="test123",
        )
        self.client.force_login(self.user)

    def test_appels_index_filters_formulaire_and_modified_by(self):
        first = Appel.objects.create(code="APP001", nom="Alpha One", locked_by=self.user, status="termine")
        second = Appel.objects.create(code="APP002", nom="Beta Two", locked_by=self.user, status="en_cours")
        AppelAnswers.objects.create(
            appel=first,
            q1_clarte_exposes=4,
            q2_interaction_formateur=4,
            q3_maitrise_contenu=4,
            q4_salle_adequate=4,
            q5_materiel_disponible=4,
            q6_organisation_temps=4,
            q7_utilite_formation=4,
            q8_adequation_besoins=4,
            q9_satisfaction_globale=4,
            commentaire="RAS",
            recommandations="RAS",
            modified_by=self.modifier,
        )
        AppelAnswers.objects.create(
            appel=second,
            commentaire="Brouillon",
            recommandations="Brouillon",
            modified_by=self.modifier,
        )

        response = self.client.get(
            reverse("appels_index"),
            {"formulaire": "rempli", "modified_by": self.modifier.username, "q": "APP001"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "APP001")
        self.assertNotContains(response, "APP002")

    def test_appels_index_hides_missing_audio_files(self):
        Appel.objects.create(
            code="APP404",
            nom="Audio Missing",
            status="termine",
            audio_file="padesce/2026/03/18/missing-audio.webm",
        )

        response = self.client.get(reverse("appels_index"), {"q": "APP404"})

        self.assertEqual(response.status_code, 200)
        row = next(item for item in response.context["appels"] if item.code == "APP404")
        self.assertFalse(row.has_audio_file)
        self.assertEqual(row.audio_file_url, "")
        self.assertContains(response, "Audio introuvable")
        self.assertNotContains(response, "missing-audio.webm")
