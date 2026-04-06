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
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


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
        first = Appel.objects.create(code="APP001", nom="Alpha One", locked_by=self.user, status="formulaire_rempli")
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

    def test_appels_index_treats_single_answer_as_filled_form(self):
        appel = Appel.objects.create(code="APP003", nom="Gamma Three", locked_by=self.user, status="appel_tente")
        AppelAnswers.objects.create(
            appel=appel,
            q1_clarte_exposes=5,
            commentaire="Premier point repondu",
            recommandations="RAS",
            modified_by=self.modifier,
        )

        response = self.client.get(reverse("appels_index"), {"formulaire": "rempli", "q": "APP003"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "APP003")

    def test_appels_index_completed_filter_includes_all_finalized_statuses(self):
        Appel.objects.create(code="APP005", nom="Echo Five", locked_by=self.user, status="appel_reussi")
        Appel.objects.create(code="APP006", nom="Foxtrot Six", locked_by=self.user, status="formulaire_rempli")
        Appel.objects.create(code="APP007", nom="Golf Seven", locked_by=self.user, status="formulaire_avec_audio")
        Appel.objects.create(code="APP008", nom="Hotel Eight", locked_by=self.user, status="a_rappeler")

        response = self.client.get(reverse("appels_index"), {"status": "completed"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "APP005")
        self.assertContains(response, "APP006")
        self.assertContains(response, "APP007")
        self.assertNotContains(response, "APP008")

    def test_appel_answers_detail_syncs_status_after_single_answer(self):
        appel = Appel.objects.create(code="APP004", nom="Delta Four", locked_by=self.user, status="appel_tente")

        response = self.client.post(
            reverse("appel_answers_detail", args=[appel.pk]),
            {
                "q1": "4",
                "commentaire": "Reponse partielle",
                "recommandations": "RAS",
            },
        )

        self.assertEqual(response.status_code, 200)
        appel.refresh_from_db()
        self.assertEqual(appel.status, "formulaire_rempli")

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

    @patch("App_PADESCE.appels.views.build_padesce_source_index")
    def test_appels_index_hides_reached_classes_and_ignores_learners_without_phone(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {"label": "Fichier consolide", "modified_label": "27/03/2026 a 12:20"},
            "classes": {
                "cla001": {"classe_id": "CLA001", "prestation_id": "PRESTA001", "statut_prestation": "TERMINE"},
                "cla002": {"classe_id": "CLA002", "prestation_id": "PRESTA001", "statut_prestation": "TERMINE"},
            },
            "prestations": {
                "presta001": {"prestation_id": "PRESTA001", "statut_prestation": "TERMINE"},
            },
            "records": {
                "a1": {"classe_id": "CLA001", "telephone1": "690000001", "telephone2": ""},
                "a2": {"classe_id": "CLA001", "telephone1": "690000002", "telephone2": ""},
                "a3": {"classe_id": "CLA001", "telephone1": "", "telephone2": ""},
                "b1": {"classe_id": "CLA002", "telephone1": "690000010", "telephone2": ""},
            },
        }

        Appel.objects.create(code="CLA001-A", nom="Alpha", classe_label="CLA001", telephone1="690000001", status="formulaire_rempli")
        Appel.objects.create(code="CLA001-B", nom="Bravo", classe_label="CLA001", telephone1="690000002", status="en_attente")
        Appel.objects.create(code="CLA001-C", nom="Charlie", classe_label="CLA001", telephone1="", status="en_attente")
        Appel.objects.create(code="CLA002-A", nom="Delta", classe_label="CLA002", telephone1="690000010", status="en_attente")

        response = self.client.get(reverse("appels_index"))

        self.assertEqual(response.status_code, 200)
        visible_classes = {row.classe_label for row in response.context["appels"]}
        self.assertEqual(visible_classes, {"CLA002"})
        self.assertEqual(
            [item["value"] for item in response.context["filters"]["classes_enriched"]],
            ["CLA002"],
        )
        classe_progress = {
            item["classe"]: item
            for item in response.context["classe_progress"]
        }
        self.assertEqual(classe_progress["CLA001"]["total"], 2)
        self.assertTrue(classe_progress["CLA001"]["reached"])

    @patch("App_PADESCE.appels.views.build_padesce_source_index")
    def test_appels_index_uses_saved_forms_for_25_percent_threshold(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {"label": "Fichier consolide", "modified_label": "27/03/2026 a 12:20"},
            "classes": {
                "cla100": {"classe_id": "CLA100", "prestation_id": "PRESTA100", "statut_prestation": "TERMINE"},
            },
            "prestations": {
                "presta100": {"prestation_id": "PRESTA100", "statut_prestation": "TERMINE"},
            },
            "records": {
                "a1": {"classe_id": "CLA100", "telephone1": "690100001", "telephone2": ""},
                "a2": {"classe_id": "CLA100", "telephone1": "690100002", "telephone2": ""},
                "a3": {"classe_id": "CLA100", "telephone1": "690100003", "telephone2": ""},
                "a4": {"classe_id": "CLA100", "telephone1": "690100004", "telephone2": ""},
            },
        }

        counted_row = Appel.objects.create(
            code="CLA100-A",
            nom="Alpha",
            classe_label="CLA100",
            telephone1="690100001",
            status="appel_reussi",
        )
        Appel.objects.create(code="CLA100-B", nom="Bravo", classe_label="CLA100", telephone1="690100002", status="en_attente")
        Appel.objects.create(code="CLA100-C", nom="Charlie", classe_label="CLA100", telephone1="690100003", status="en_attente")
        Appel.objects.create(code="CLA100-D", nom="Delta", classe_label="CLA100", telephone1="690100004", status="en_attente")

        response = self.client.get(reverse("appels_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual({row.classe_label for row in response.context["appels"]}, {"CLA100"})
        classe_progress = {item["classe"]: item for item in response.context["classe_progress"]}
        self.assertEqual(classe_progress["CLA100"]["termines"], 0)
        self.assertFalse(classe_progress["CLA100"]["reached"])

        counted_row.status = "formulaire_rempli"
        counted_row.save(update_fields=["status"])

        response = self.client.get(reverse("appels_index"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["filters"]["classes_enriched"]), [])
        self.assertEqual(list(response.context["appels"]), [])

    @patch("App_PADESCE.appels.views.build_padesce_source_index")
    def test_appels_index_recommends_last_class_to_finish_prestation(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {"label": "Fichier consolide", "modified_label": "27/03/2026 a 12:20"},
            "classes": {
                "cla010": {
                    "classe_id": "CLA010",
                    "prestation_id": "PRESTA010",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "statut_prestation": "TERMINE",
                },
                "cla011": {
                    "classe_id": "CLA011",
                    "prestation_id": "PRESTA010",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "statut_prestation": "TERMINE",
                },
                "cla012": {
                    "classe_id": "CLA012",
                    "prestation_id": "PRESTA010",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "statut_prestation": "TERMINE",
                },
                "cla020": {
                    "classe_id": "CLA020",
                    "prestation_id": "PRESTA020",
                    "prestataire": "Prestataire B",
                    "beneficiaire": "Beneficiaire B",
                    "statut_prestation": "TERMINE",
                },
            },
            "prestations": {
                "presta010": {
                    "prestation_id": "PRESTA010",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "statut_prestation": "TERMINE",
                },
                "presta020": {
                    "prestation_id": "PRESTA020",
                    "prestataire": "Prestataire B",
                    "beneficiaire": "Beneficiaire B",
                    "statut_prestation": "TERMINE",
                },
            },
            "records": {
                "a1": {"classe_id": "CLA010", "telephone1": "690100001", "telephone2": ""},
                "a2": {"classe_id": "CLA010", "telephone1": "690100002", "telephone2": ""},
                "b1": {"classe_id": "CLA011", "telephone1": "690110001", "telephone2": ""},
                "b2": {"classe_id": "CLA011", "telephone1": "690110002", "telephone2": ""},
                "c1": {"classe_id": "CLA012", "telephone1": "690120001", "telephone2": ""},
                "d1": {"classe_id": "CLA020", "telephone1": "690200001", "telephone2": ""},
            },
        }

        Appel.objects.create(code="CLA010-A", nom="A", classe_label="CLA010", telephone1="690100001", status="formulaire_rempli")
        Appel.objects.create(code="CLA010-B", nom="B", classe_label="CLA010", telephone1="690100002", status="en_attente")
        Appel.objects.create(code="CLA011-A", nom="C", classe_label="CLA011", telephone1="690110001", status="formulaire_rempli")
        Appel.objects.create(code="CLA011-B", nom="D", classe_label="CLA011", telephone1="690110002", status="en_attente")
        Appel.objects.create(code="CLA012-A", nom="E", classe_label="CLA012", telephone1="690120001", status="en_attente")
        Appel.objects.create(code="CLA020-A", nom="F", classe_label="CLA020", telephone1="690200001", status="en_attente")

        response = self.client.get(reverse("appels_index"))

        self.assertEqual(response.status_code, 200)
        recommendations = response.context["recommended_classes"]
        self.assertGreaterEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["classe"], "CLA012")
        self.assertEqual(recommendations[0]["priority_label"], "Prestation a finir")


class AppelActionFlagTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="appels-agent",
            password="test123",
        )
        self.client.force_login(self.user)

    def test_appel_action_persists_not_formed_flag(self):
        appel = Appel.objects.create(
            code="APP-FLAG-001",
            nom="Apprenant Non Forme",
            status="en_attente",
            is_active=True,
        )

        response = self.client.post(
            reverse("appel_action", args=[appel.pk]),
            {"action": "terminer", "flag_pas_forme": "1"},
        )

        self.assertEqual(response.status_code, 200)
        appel.refresh_from_db()
        self.assertTrue(appel.flag_pas_forme)

    def test_appel_action_start_marks_call_in_progress(self):
        appel = Appel.objects.create(
            code="APP-FLAG-002",
            nom="Apprenant En Cours",
            status="en_attente",
            is_active=True,
        )

        response = self.client.post(
            reverse("appel_action", args=[appel.pk]),
            {"action": "start"},
        )

        self.assertEqual(response.status_code, 200)
        appel.refresh_from_db()
        self.assertEqual(appel.status, "en_cours")


class AppelFinalizeSaveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="appels-finalize-agent",
            password="test123",
        )
        self.client.force_login(self.user)

    def test_finalize_saves_form_when_questions_are_submitted_without_form_modified_flag(self):
        Appel.objects.create(
            code="APP-FINAL-002",
            nom="Autre Apprenant",
            classe_label="CLA-FINAL",
            telephone1="690000001",
            status="en_attente",
            is_active=True,
        )
        appel = Appel.objects.create(
            code="APP-FINAL-001",
            nom="Apprenant Test",
            classe_label="CLA-FINAL",
            telephone1="690000002",
            status="en_cours",
            is_active=True,
        )

        response = self.client.post(
            reverse("appel_finalize", args=[appel.pk]),
            {
                "action": "terminer",
                "q1": "4",
                "q9": "5",
                "commentaire": "Formulaire PADESCE bien renseigne",
                "recommandations": "Continuer comme cela",
                "form_modified": "0",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        appel.refresh_from_db()
        answers = appel.answers

        self.assertEqual(appel.status, "formulaire_rempli")
        self.assertEqual(payload["status"], "formulaire_rempli")
        self.assertFalse(payload["satisfaction_saved"])
        self.assertEqual(answers.q1_clarte_exposes, 4)
        self.assertEqual(answers.q9_satisfaction_globale, 5)
        self.assertEqual(answers.commentaire, "Formulaire PADESCE bien renseigne")
        self.assertEqual(answers.recommandations, "Continuer comme cela")
        self.assertFalse(SatisfactionApprenant.objects.filter(appel=appel).exists())
        self.assertEqual(payload["class_progress"]["termines"], 1)
        self.assertEqual(payload["class_progress"]["target"], 1)
        self.assertTrue(payload["class_progress"]["reached"])

    def test_finalize_without_questionnaire_answers_marks_call_successful(self):
        appel = Appel.objects.create(
            code="APP-FINAL-003",
            nom="Apprenant Sans Formulaire",
            classe_label="CLA-FINAL-2",
            telephone1="690000003",
            status="en_cours",
            is_active=True,
        )

        response = self.client.post(
            reverse("appel_finalize", args=[appel.pk]),
            {
                "action": "terminer",
                "commentaire": "Pas de notes disponibles",
                "recommandations": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        appel.refresh_from_db()

        self.assertEqual(appel.status, "appel_reussi")
        self.assertEqual(payload["status"], "appel_reussi")
        self.assertFalse(payload["satisfaction_saved"])
        self.assertFalse(SatisfactionApprenant.objects.filter(appel=appel).exists())
