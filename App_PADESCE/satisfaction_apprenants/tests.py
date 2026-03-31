import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase

from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.formations.models import Beneficiaire, Classe, Formation, Inspecteur, Lieu, Prestataire, Prestation
from App_PADESCE.satisfaction_apprenants.management.commands.import_satisfaction_excel import _sync_source_models
from App_PADESCE.satisfaction_apprenants.views import (
    _attach_network_source_to_rows,
    _build_dashboard_filter_options,
    _build_threshold_class_stats,
    _call_report_status,
    _dashboard_export_filename,
    _dashboard_export_filename_from_rows,
    _assign_enquete_ids,
    _merge_class_apprenant_counts,
    _qualified_prestation_codes_from_source,
    _source_class_apprenant_counts,
    _terminated_prestation_codes_from_source,
    satisfaction_dashboard_rag,
)


class SatisfactionDashboardSourceTests(SimpleTestCase):
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index")
    def test_attach_network_source_to_rows_adds_apprenant_id_and_coherence(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {
                "name": "fichier consolide.xlsm",
                "modified_label": "24/03/2026 a 10:30",
            },
            "counts": {"apprenants": 2, "classes": 1, "prestations": 1},
            "duplicate_codes": [],
            "records": {
                "ab0e": {
                    "apprenant_id": "APP001",
                    "nom_individu": "Fanta Adamou",
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA072",
                    "prestataire": "Prestataire Alpha",
                    "beneficiaire": "Beneficiaire Beta",
                    "fenetre": "2",
                    "cohorte": "1",
                    "statut_prestation": "TERMINE",
                }
            },
        }

        rows, summary = _attach_network_source_to_rows(
            [
                {
                    "apprenant_code": "AB0E",
                    "apprenant_nom": "Fanta Adamou",
                    "classe_code": "CLA001",
                    "formation_intitule": "Transformation des produits laitiers",
                    "prestation_code": "PRESTA072",
                    "prestataire": "Prestataire Alpha",
                    "beneficiaire": "Beneficiaire Beta",
                },
                {
                    "apprenant_code": "MISS001",
                    "apprenant_nom": "Nom absent",
                    "classe_code": "CLA999",
                    "prestation_code": "PRESTA999",
                    "prestataire": "Autre prestataire",
                    "beneficiaire": "Autre beneficiaire",
                },
            ]
        )

        self.assertEqual(rows[0]["source_apprenant_id"], "APP001")
        self.assertEqual(rows[0]["source_status_label"], "OK")
        self.assertEqual(rows[0]["formation_intitule"], "Transformation des produits laitiers")
        self.assertEqual(rows[0]["source_statut_prestation"], "TERMINE")
        self.assertEqual(rows[1]["source_status_label"], "Absent source")
        self.assertEqual(summary["matched_count"], 1)
        self.assertEqual(summary["missing_count"], 1)
        self.assertEqual(summary["apprenant_id_count"], 1)

    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index")
    def test_attach_network_source_to_rows_flags_mismatch(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {
                "name": "fichier consolide.xlsm",
                "modified_label": "24/03/2026 a 10:30",
            },
            "counts": {"apprenants": 1, "classes": 1, "prestations": 1},
            "duplicate_codes": [],
            "records": {
                "ab0e": {
                    "apprenant_id": "APP001",
                    "nom_individu": "Fanta Adamou",
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA072",
                    "prestataire": "Prestataire Alpha",
                    "beneficiaire": "Beneficiaire Beta",
                }
            },
        }

        rows, summary = _attach_network_source_to_rows(
            [
                {
                    "apprenant_code": "AB0E",
                    "apprenant_nom": "Autre nom",
                    "classe_code": "CLA001",
                    "formation_intitule": "Formation test",
                    "prestation_code": "PRESTA072",
                    "prestataire": "Prestataire Alpha",
                    "beneficiaire": "Beneficiaire Beta",
                }
            ]
        )

        self.assertEqual(rows[0]["source_status_label"], "À vérifier")
        self.assertIn("Nom:", rows[0]["source_alerts_label"])
        self.assertEqual(summary["mismatch_count"], 1)

    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index")
    def test_attach_network_source_to_rows_uses_requested_source_key(self, mock_build_source_index):
        mock_build_source_index.return_value = {
            "source": {
                "key": "cutoff",
                "label": "Fichier consolide CutOff",
                "name": "fichier consolide CutOff.xlsm",
                "modified_label": "27/03/2026 a 12:20",
            },
            "counts": {"apprenants": 0, "classes": 0, "prestations": 0},
            "duplicate_codes": [],
            "records": {},
        }

        _attach_network_source_to_rows([], source_key="cutoff")

        mock_build_source_index.assert_called_once_with(source_key="cutoff")

    def test_source_class_apprenant_counts_ignores_records_without_phone(self):
        counts = _source_class_apprenant_counts(
            {
                "records": {
                    "a1": {"classe_id": "CLA001", "telephone1": "690000001", "telephone2": ""},
                    "a2": {"classe_id": "CLA001", "telephone1": "", "telephone2": ""},
                    "a3": {"classe_id": "CLA001", "telephone1": "", "telephone2": "699000002"},
                    "b1": {"classe_id": "CLA002", "telephone1": "", "telephone2": ""},
                }
            }
        )

        self.assertEqual(counts["CLA001"], 2)
        self.assertNotIn("CLA002", counts)

    def test_build_dashboard_filter_options_limits_other_filters_to_related_values(self):
        rows = [
            {
                "classe_code": "CLA001",
                "formation_intitule": "Formation A",
                "classe_intitule": "Formation A",
                "prestation_code": "PRESTA001",
                "prestataire": "Prestataire A",
                "beneficiaire": "Beneficiaire A",
                "cohorte": "1",
                "ville": "Garoua",
                "user": "agent-a",
                "q9_satisfaction_globale": 5,
            },
            {
                "classe_code": "CLA001",
                "formation_intitule": "Formation A",
                "classe_intitule": "Formation A",
                "prestation_code": "PRESTA001",
                "prestataire": "Prestataire A",
                "beneficiaire": "Beneficiaire A",
                "cohorte": "1",
                "ville": "Garoua",
                "user": "agent-b",
                "q9_satisfaction_globale": 4,
            },
            {
                "classe_code": "CLA002",
                "formation_intitule": "Formation B",
                "classe_intitule": "Formation B",
                "prestation_code": "PRESTA002",
                "prestataire": "Prestataire B",
                "beneficiaire": "Beneficiaire B",
                "cohorte": "2",
                "ville": "Maroua",
                "user": "agent-c",
                "q9_satisfaction_globale": 5,
            },
            {
                "classe_code": "CLA002",
                "formation_intitule": "Formation B",
                "classe_intitule": "Formation B",
                "prestation_code": "PRESTA002",
                "prestataire": "Prestataire B",
                "beneficiaire": "Beneficiaire B",
                "cohorte": "2",
                "ville": "Maroua",
                "user": "agent-d",
                "q9_satisfaction_globale": 4,
            },
        ]

        filter_options = _build_dashboard_filter_options(
            rows,
            {
                "prestation": "",
                "ville": "",
                "user": "",
                "classe": "CLA002",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            {"CLA001": 2, "CLA002": 2},
        )

        self.assertEqual(filter_options["prestataire"], ["Prestataire B"])
        self.assertEqual(filter_options["beneficiaire"], ["Beneficiaire B"])
        self.assertEqual(filter_options["cohorte"], ["2"])

    def test_build_threshold_class_stats_merges_duplicate_class_codes(self):
        classe_stats, threshold_codes = _build_threshold_class_stats(
            [
                {
                    "classe_code": "CLA012",
                    "formation_intitule": "Gestion d'entreprise",
                    "classe_intitule": "Gestion d'entreprise",
                    "prestation_code": "PRESTA012",
                    "cohorte": "1",
                    "q9_satisfaction_globale": 5,
                },
                {
                    "classe_code": "CLA012",
                    "formation_intitule": "-",
                    "classe_intitule": "-",
                    "prestation_code": "PRESTA012",
                    "cohorte": "1",
                    "q9_satisfaction_globale": 4,
                },
            ],
            {"CLA012": 2},
        )

        self.assertEqual(len(classe_stats), 1)
        self.assertEqual(classe_stats[0]["code"], "CLA012")
        self.assertEqual(classe_stats[0]["intitule"], "Gestion d'entreprise")
        self.assertEqual(classe_stats[0]["nb"], 2)
        self.assertEqual(threshold_codes, {"CLA012"})

    def test_qualified_prestation_codes_from_source_requires_all_source_classes(self):
        qualified = _qualified_prestation_codes_from_source(
            {
                "prestation": "",
                "fenetre": "",
                "ville": "",
                "user": "",
                "classe": "",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            [
                {"code": "CLA001", "prestation": "PRESTA001", "threshold_reached": True},
                {"code": "CLA002", "prestation": "PRESTA001", "threshold_reached": False},
                {"code": "CLA003", "prestation": "PRESTA002", "threshold_reached": True},
            ],
            {
                "classes": {
                    "cla001": {"classe_id": "CLA001", "prestation_id": "PRESTA001"},
                    "cla002": {"classe_id": "CLA002", "prestation_id": "PRESTA001"},
                    "cla003": {"classe_id": "CLA003", "prestation_id": "PRESTA002"},
                }
            },
        )

        self.assertEqual(qualified, {"presta002"})

    def test_qualified_prestation_codes_from_source_excludes_arrete_status(self):
        qualified = _qualified_prestation_codes_from_source(
            {
                "prestation": "",
                "fenetre": "",
                "ville": "",
                "user": "",
                "classe": "",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            [
                {"code": "CLA001", "prestation": "PRESTA001", "threshold_reached": True},
                {"code": "CLA002", "prestation": "PRESTA001", "threshold_reached": True},
                {"code": "CLA003", "prestation": "PRESTA002", "threshold_reached": True},
            ],
            {
                "classes": {
                    "cla001": {"classe_id": "CLA001", "prestation_id": "PRESTA001", "statut_prestation": "TERMINÉ"},
                    "cla002": {"classe_id": "CLA002", "prestation_id": "PRESTA001", "statut_prestation": "EN COURS"},
                    "cla003": {"classe_id": "CLA003", "prestation_id": "PRESTA002", "statut_prestation": "ARRETÉ"},
                }
            },
        )

        self.assertEqual(qualified, set())

    def test_terminated_prestation_codes_from_source_counts_only_terminated_statuses(self):
        terminated = _terminated_prestation_codes_from_source(
            {
                "prestation": "",
                "fenetre": "",
                "ville": "",
                "user": "",
                "classe": "",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            {
                "classes": {
                    "cla001": {"classe_id": "CLA001", "prestation_id": "PRESTA001", "statut_prestation": "TERMINÉ"},
                    "cla002": {"classe_id": "CLA002", "prestation_id": "PRESTA001", "statut_prestation": "EN COURS"},
                    "cla003": {"classe_id": "CLA003", "prestation_id": "PRESTA002", "statut_prestation": "ARRETÉ"},
                }
            },
        )

        self.assertEqual(terminated, set())

    def test_merge_class_apprenant_counts_prefers_network_counts(self):
        merged = _merge_class_apprenant_counts(
            {"CLA001": 2, "CLA003": 4},
            {
                "records": {
                    "a": {"classe_id": "CLA001", "telephone1": "690000001"},
                    "b": {"classe_id": "CLA001", "telephone2": "690000002"},
                    "c": {"classe_id": "CLA001", "telephone1": "690000003"},
                    "d": {"classe_id": "CLA002", "telephone1": "690000010"},
                }
            },
        )

        self.assertEqual(merged["CLA001"], 3)
        self.assertEqual(merged["CLA002"], 1)
        self.assertEqual(merged["CLA003"], 4)

    def test_call_report_status_marks_ras_only_form_as_failure(self):
        appel = SimpleNamespace(
            status="termine",
            deja_forme=False,
            flag_pas_forme=False,
            flag_faux_nom=False,
            flag_vrai_nom="",
            flag_numero_double=False,
            flag_deja_appele=False,
            get_status_display=lambda: "Termine",
        )
        answer = SimpleNamespace(
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
        )

        is_success, reasons = _call_report_status(appel, answer)

        self.assertFalse(is_success)
        self.assertIn("Formulaire RAS", reasons)

    def test_dashboard_export_filename_matches_expected_pattern(self):
        filename = _dashboard_export_filename(
            {
                "classe": "CLA002",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            "csv",
        )

        self.assertEqual(filename, "CLA002_TOUS_TOUS_TOUTES.csv")

    def test_assign_enquete_ids_uses_network_ids_then_fallback(self):
        rows = _assign_enquete_ids(
            [
                {
                    "classe_code": "CLA005",
                    "modified_at": 1,
                    "survey_date": None,
                    "survey_time": None,
                    "source_known_enquete_ids": ["ENQ1", "ENQ2"],
                },
                {
                    "classe_code": "CLA005",
                    "modified_at": 2,
                    "survey_date": None,
                    "survey_time": None,
                    "source_known_enquete_ids": ["ENQ1", "ENQ2"],
                },
                {
                    "classe_code": "CLA005",
                    "modified_at": 3,
                    "survey_date": None,
                    "survey_time": None,
                    "source_known_enquete_ids": ["ENQ1", "ENQ2"],
                },
            ]
        )

        self.assertEqual(rows[0]["source_enquete_id"], "ENQ001")
        self.assertEqual(rows[1]["source_enquete_id"], "ENQ002")
        self.assertEqual(rows[2]["source_enquete_id"], "ENQ003")

    def test_dashboard_export_filename_from_rows_uses_first_row(self):
        filename = _dashboard_export_filename_from_rows(
            [
                {
                    "classe_code": "CLA005",
                    "prestataire": "Centre de formation professionnelle Pontaah",
                    "beneficiaire": "GIC Agropastoral Ketty",
                    "cohorte": "1",
                }
            ],
            {
                "classe": "CLA002",
                "prestataire": "",
                "beneficiaire": "",
                "cohorte": "",
            },
            "csv",
        )

        self.assertEqual(
            filename,
            "CLA005_CENTRE_DE_FORMATION_PROFESSIONNELLE_PONT_GIC_AGROPASTORAL_KETTY_1.csv",
        )


class SatisfactionDashboardRagTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()


class SatisfactionImportExcelSyncTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sync_source_models_creates_and_reuses_network_entities(self):
        source_record = {
            "apprenant_id": "APP001",
            "nom_individu": "Fanta Adamou",
            "classe_id": "CLA001",
            "prestation_id": "PRESTA072",
            "prestataire": "Centre de formation professionnelle Pontaah",
            "beneficiaire": "SCOOP YILLAGA YAOURT DU MAYO-KANI (COOP SYYMK)",
            "fenetre": "3",
            "cohorte": "1",
            "statut_apprenant": "Actif",
            "statut_prestation": "ARRETE",
            "formation": "Transformation des produits laitiers",
            "lieu": "COMMUNE DE MINDIF",
            "ville": "Mindif",
            "region": "EXTREME-NORD",
            "numero": "1",
            "sexe": "F",
            "inspecteur_id": "INS001",
            "inspecteur_label": "Charles Xavier",
        }
        initial_counts = {
            "formations": Formation.objects.count(),
            "prestataires": Prestataire.objects.count(),
            "beneficiaires": Beneficiaire.objects.count(),
            "lieux": Lieu.objects.count(),
            "prestations": Prestation.objects.count(),
            "classes": Classe.objects.count(),
            "inspecteurs": Inspecteur.objects.count(),
            "apprenants": Apprenant.objects.count(),
        }

        first_sync = _sync_source_models(source_record, {})

        self.assertLessEqual(Formation.objects.count(), initial_counts["formations"] + 1)
        self.assertLessEqual(Prestataire.objects.count(), initial_counts["prestataires"] + 1)
        self.assertLessEqual(Beneficiaire.objects.count(), initial_counts["beneficiaires"] + 1)
        self.assertLessEqual(Lieu.objects.count(), initial_counts["lieux"] + 1)
        self.assertLessEqual(Prestation.objects.count(), initial_counts["prestations"] + 1)
        self.assertLessEqual(Classe.objects.count(), initial_counts["classes"] + 1)
        self.assertLessEqual(Inspecteur.objects.count(), initial_counts["inspecteurs"] + 1)
        self.assertEqual(Apprenant.objects.count(), initial_counts["apprenants"] + 1)
        self.assertEqual(first_sync["classe"].code, "CLA001")
        self.assertEqual(first_sync["prestation"].code, "PRESTA072")
        self.assertEqual(first_sync["apprenant"].code, "APP001")
        self.assertEqual(first_sync["inspecteur"].code, "INS001")
        self.assertEqual(first_sync["classe"].statut, "termine")
        after_first_counts = {
            "formations": Formation.objects.count(),
            "prestataires": Prestataire.objects.count(),
            "beneficiaires": Beneficiaire.objects.count(),
            "lieux": Lieu.objects.count(),
            "prestations": Prestation.objects.count(),
            "classes": Classe.objects.count(),
            "inspecteurs": Inspecteur.objects.count(),
            "apprenants": Apprenant.objects.count(),
        }

        apprenant = first_sync["apprenant"]
        apprenant.code = "OLD001"
        apprenant.save(update_fields=["code"])

        second_sync = _sync_source_models(source_record, {})

        self.assertEqual(Formation.objects.count(), after_first_counts["formations"])
        self.assertEqual(Prestataire.objects.count(), after_first_counts["prestataires"])
        self.assertEqual(Beneficiaire.objects.count(), after_first_counts["beneficiaires"])
        self.assertEqual(Lieu.objects.count(), after_first_counts["lieux"])
        self.assertEqual(Prestation.objects.count(), after_first_counts["prestations"])
        self.assertEqual(Classe.objects.count(), after_first_counts["classes"])
        self.assertEqual(Inspecteur.objects.count(), after_first_counts["inspecteurs"])
        self.assertEqual(Apprenant.objects.count(), after_first_counts["apprenants"])
        self.assertEqual(second_sync["apprenant"].pk, apprenant.pk)
        self.assertEqual(second_sync["apprenant"].code, "APP001")
        self.assertEqual(second_sync["apprenant"].classe.code, "CLA001")

    @patch("App_PADESCE.satisfaction_apprenants.views.answer_dashboard_prompt")
    @patch("App_PADESCE.satisfaction_apprenants.views._build_satisfaction_dashboard_data")
    def test_satisfaction_dashboard_rag_returns_json_payload(self, mock_build_dashboard_data, mock_answer_dashboard_prompt):
        mock_build_dashboard_data.return_value = {
            "rows": [{"apprenant_code": "AB0E"}],
            "context": {"source_summary": {"available": True}},
            "filters": {"classe": "CLA001"},
        }
        mock_answer_dashboard_prompt.return_value = {
            "answer_markdown": "2 apprenants retrouves.",
            "matched_rows": [{"id_apprenant": "APP001", "classe": "CLA001"}],
            "retrieved_count": 4,
            "insufficient_context": False,
            "model": "openai/gpt-oss-20b",
        }

        request = self.factory.post(
            "/satisfaction-apprenants/analyse/rag/",
            data=json.dumps(
                {
                    "prompt": "Affiche les apprenants de la cohorte 1",
                    "tab": "tab-apprenants",
                    "filter_query": "classe=CLA001&cohorte=1",
                }
            ),
            content_type="application/json",
        )
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

        response = satisfaction_dashboard_rag(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["active_tab"], "tab-apprenants")
        self.assertEqual(payload["matched_count"], 1)
        self.assertEqual(payload["row_count"], 1)
        mock_answer_dashboard_prompt.assert_called_once_with(
            "Affiche les apprenants de la cohorte 1",
            "tab-apprenants",
            {"source_summary": {"available": True}},
            [{"apprenant_code": "AB0E"}],
        )

    def test_satisfaction_dashboard_rag_rejects_empty_prompt(self):
        request = self.factory.post(
            "/satisfaction-apprenants/analyse/rag/",
            data=json.dumps({"prompt": "   "}),
            content_type="application/json",
        )
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

        response = satisfaction_dashboard_rag(request)

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["error"], "Le prompt est vide.")

    def test_satisfaction_dashboard_rag_forbids_non_manager_user(self):
        request = self.factory.post(
            "/satisfaction-apprenants/analyse/rag/",
            data=json.dumps({"prompt": "Liste les apprenants"}),
            content_type="application/json",
        )
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            groups=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(exists=lambda: False)),
        )

        response = satisfaction_dashboard_rag(request)

        self.assertEqual(response.status_code, 403)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(
            payload["error"],
            "Acces reserve aux superadmins et aux managers PADESCE/CGA.",
        )
