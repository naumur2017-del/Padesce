import io
import json
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import QueryDict
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from docx import Document

from App_PADESCE.appels.models import Appel, AppelAnswers
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.analysis_rules import appel_is_manually_excluded
from App_PADESCE.formations.models import Beneficiaire, Classe, Formation, Inspecteur, Lieu, Prestataire, Prestation
from App_PADESCE.satisfaction_apprenants.management.commands.import_satisfaction_excel import _sync_source_models
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant
from App_PADESCE.satisfaction_apprenants.services import get_prestations_ranking
from App_PADESCE.satisfaction_apprenants.views import (
    _analysis_selected_source,
    _attach_network_source_to_rows,
    _build_satisfaction_dashboard_data,
    _build_missing_prestations_analysis,
    _build_dashboard_filter_options,
    _build_threshold_class_stats,
    _call_report_status,
    _dashboard_chapeau_title,
    _dashboard_export_filename,
    _dashboard_export_filename_from_rows,
    _assign_enquete_ids,
    _merge_class_apprenant_counts,
    _qualified_prestation_codes_from_source,
    _safe_import_appel_code,
    _source_class_apprenant_counts,
    _terminated_prestation_codes_from_source,
    satisfaction_dashboard_export_chapeau,
    satisfaction_dashboard_rag,
)


class SatisfactionDashboardSourceTests(SimpleTestCase):
    def test_analysis_selected_source_defaults_to_cutoff(self):
        source = _analysis_selected_source(SimpleNamespace(GET=QueryDict("", mutable=True)))

        self.assertEqual(source, "cutoff")

    @patch("App_PADESCE.satisfaction_apprenants.views._build_satisfaction_dashboard_data")
    def test_export_chapeau_prefixes_table_title_with_enquete_label(self, mock_dashboard):
        class_label = (
            "CLA001_CENTRE DE FORMATION PROFESSIONNELLE PONTAAH_"
            "SCOOP YILLAGA YAOURT DU MAYO-KANI (COOP SYYMK)"
        )
        mock_dashboard.return_value = {
            "filters": {},
            "rows": [
                {
                    "classe_code": "CLA001",
                    "source_apprenant_id": "APP001",
                    "apprenant_nom": "Amina",
                    "prestataire": "CENTRE DE FORMATION PROFESSIONNELLE PONTAAH",
                    "beneficiaire": "SCOOP YILLAGA YAOURT DU MAYO-KANI (COOP SYYMK)",
                    "q1_clarte_formateur": 4,
                }
            ],
            "context": {
                "classe_stats": [
                    {
                        "code": "CLA001",
                        "avgs": [4] + [0] * 8,
                    }
                ]
            },
        }
        request = RequestFactory().get("/satisfaction-apprenants/analyse/export/chapeau/")
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

        response = satisfaction_dashboard_export_chapeau(request)

        self.assertEqual(response.status_code, 200)
        document = Document(io.BytesIO(response.content))
        self.assertEqual(
            document.tables[0].rows[0].cells[0].text,
            _dashboard_chapeau_title(class_label),
        )

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
                    "telephone1": "690000001",
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
        self.assertEqual(summary["source_apprenant_count"], 1)

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
                    "telephone1": "690000001",
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

    def test_terminated_prestation_codes_from_source_ignores_classes_without_phone(self):
        terminated_codes = _terminated_prestation_codes_from_source(
            {},
            {
                "classes": {
                    "cla001": {
                        "classe_id": "CLA001",
                        "prestation_id": "PRESTA001",
                        "statut_prestation": "TERMINE",
                    },
                    "cla002": {
                        "classe_id": "CLA002",
                        "prestation_id": "PRESTA002",
                        "statut_prestation": "TERMINE",
                    },
                },
                "records": {
                    "a1": {"classe_id": "CLA001", "telephone1": "", "telephone2": ""},
                    "b1": {"classe_id": "CLA002", "telephone1": "690000111", "telephone2": ""},
                },
            },
        )

        self.assertEqual(terminated_codes, {"presta002"})

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

    def test_build_threshold_class_stats_uses_external_threshold_codes(self):
        classe_stats, threshold_codes = _build_threshold_class_stats(
            [
                {
                    "classe_code": "CLA099",
                    "formation_intitule": "Formation Z",
                    "classe_intitule": "Formation Z",
                    "prestation_code": "PRESTA099",
                    "cohorte": "1",
                    "q9_satisfaction_globale": 5,
                }
            ],
            {"CLA099": 8},
            threshold_class_codes={"cla099"},
        )

        self.assertTrue(classe_stats[0]["threshold_reached"])
        self.assertEqual(threshold_codes, {"CLA099"})

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
                },
                "records": {
                    "a1": {"classe_id": "CLA001", "telephone1": "690000001"},
                    "a2": {"classe_id": "CLA002", "telephone1": "690000002"},
                    "a3": {"classe_id": "CLA003", "telephone1": "690000003"},
                },
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
                },
                "records": {
                    "a1": {"classe_id": "CLA001", "telephone1": "690000001"},
                    "a2": {"classe_id": "CLA002", "telephone1": "690000002"},
                    "a3": {"classe_id": "CLA003", "telephone1": "690000003"},
                },
            },
        )

        self.assertEqual(qualified, set())

    def test_qualified_prestation_codes_from_source_uses_status_threshold_codes(self):
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
            [],
            {
                "classes": {
                    "cla001": {
                        "classe_id": "CLA001",
                        "prestation_id": "PRESTA001",
                        "statut_prestation": "TERMINE",
                    },
                    "cla002": {
                        "classe_id": "CLA002",
                        "prestation_id": "PRESTA001",
                        "statut_prestation": "TERMINE",
                    },
                },
                "records": {
                    "a1": {"classe_id": "CLA001", "telephone1": "690000001"},
                    "a2": {"classe_id": "CLA002", "telephone1": "690000002"},
                },
            },
            threshold_class_codes={"cla001", "cla002"},
        )

        self.assertEqual(qualified, {"presta001"})

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

        self.assertEqual(merged["cla001"], 3)
        self.assertEqual(merged["cla002"], 1)
        self.assertEqual(merged["cla003"], 4)

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


class SatisfactionDashboardRegressionTests(SimpleTestCase):
    @patch("App_PADESCE.satisfaction_apprenants.views._build_dashboard_table_details", return_value={})
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._build_missing_prestations_analysis",
        return_value={"available": False, "total_missing": 0, "total_source": 0},
    )
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._build_dashboard_active_filters_summary",
        return_value=[],
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._build_class_filter_options", return_value=[])
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._build_dashboard_filter_options",
        return_value={
            "prestation": [],
            "fenetre": [],
            "ville": [],
            "user": [],
            "classe": [],
            "prestataire": [],
            "beneficiaire": [],
            "cohorte": [],
        },
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._assign_enquete_ids", side_effect=lambda rows: rows)
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._attach_network_source_to_rows",
        side_effect=lambda rows, **kwargs: (rows, {"available": False}),
    )
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index", return_value=None)
    @patch("App_PADESCE.satisfaction_apprenants.views.get_workbook_source_options", return_value=[])
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._qualified_prestation_codes_from_source",
        return_value={"presta001"},
    )
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._status_threshold_class_codes",
        return_value={"cla001"},
    )
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._terminated_prestation_codes_from_source",
        return_value={"presta001"},
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._thresholded_dashboard_rows")
    @patch("App_PADESCE.satisfaction_apprenants.views._dashboard_row_from_answer")
    @patch("App_PADESCE.satisfaction_apprenants.views._satisfaction_dashboard_base_queryset", return_value=[object()])
    @patch("App_PADESCE.satisfaction_apprenants.views._local_analysis_class_counts")
    def test_build_satisfaction_dashboard_data_sets_prestation_effectif_from_associated_classes(
        self,
        mock_class_counts,
        _mock_base_queryset,
        mock_dashboard_row_from_answer,
        mock_thresholded_dashboard_rows,
        _mock_terminated,
        _mock_threshold_codes,
        _mock_qualified,
        _mock_source_options,
        _mock_source_index,
        _mock_attach_network_rows,
        _mock_assign_enquete_ids,
        _mock_filter_options,
        _mock_class_filter_options,
        _mock_active_filter_summary,
        _mock_missing_analysis,
        _mock_table_details,
    ):
        row = {
            "fenetre": "2",
            "prestation_code": "PRESTA001",
            "prestataire": "Prestataire A",
            "beneficiaire": "Beneficiaire A",
            "classe_code": "CLA001",
            "formation_intitule": "Formation A",
            "classe_intitule": "Formation A",
            "cohorte": "1",
            "ville": "Garoua",
            "user": "agent-a",
            "modified_at": 1,
            "q1_clarte_exposes": 5,
            "q2_interaction_formateur": 4,
            "q3_maitrise_contenu": 4,
            "q4_salle_adequate": 5,
            "q5_materiel_disponible": 4,
            "q6_organisation_temps": 5,
            "q7_utilite_formation": 4,
            "q8_adequation_besoins": 5,
            "q9_satisfaction_globale": 5,
        }
        mock_class_counts.return_value = {"cla001": 2}
        mock_dashboard_row_from_answer.return_value = row
        mock_thresholded_dashboard_rows.return_value = (
            [row],
            [
                {
                    "code": "CLA001",
                    "intitule": "Formation A",
                    "prestation": "PRESTA001",
                    "cohorte": "1",
                    "nb": 1,
                    "avgs": [4.56] * 9,
                    "total_apprenants": 2,
                    "threshold_reached": True,
                }
            ],
        )

        request = SimpleNamespace(GET=QueryDict("", mutable=True))

        dashboard = _build_satisfaction_dashboard_data(request)

        self.assertEqual(dashboard["context"]["prestation_stats"][0]["effectif"], 2)
        self.assertEqual(dashboard["context"]["prestation_stats_all"][0]["effectif"], 2)

    @patch("App_PADESCE.satisfaction_apprenants.views._build_table_details_context", return_value={})
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._build_missing_prestations_analysis",
        return_value={"available": True, "total_source": 75, "total_qualified": 47, "total_missing": 28},
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._build_dashboard_active_filters_summary", return_value=[])
    @patch("App_PADESCE.satisfaction_apprenants.views._build_class_filter_options", return_value=[])
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._build_dashboard_filter_options",
        return_value={
            "prestation": [],
            "fenetre": [],
            "ville": [],
            "user": [],
            "classe": [],
            "prestataire": [],
            "beneficiaire": [],
            "cohorte": [],
            "status": [],
        },
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._assign_enquete_ids", side_effect=lambda rows: rows)
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._attach_network_source_to_rows",
        side_effect=lambda rows, **kwargs: (rows, {"available": False}),
    )
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index", return_value=None)
    @patch("App_PADESCE.satisfaction_apprenants.views.get_workbook_source_options", return_value=[])
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._qualified_prestation_codes_from_source",
        return_value={"presta001"},
    )
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._status_threshold_class_codes",
        return_value={"cla001"},
    )
    @patch(
        "App_PADESCE.satisfaction_apprenants.views._terminated_prestation_codes_from_source",
        return_value={"presta001"},
    )
    @patch("App_PADESCE.satisfaction_apprenants.views._thresholded_dashboard_rows")
    @patch("App_PADESCE.satisfaction_apprenants.views._dashboard_row_from_answer")
    @patch("App_PADESCE.satisfaction_apprenants.views._satisfaction_dashboard_base_queryset", return_value=[object()])
    @patch("App_PADESCE.satisfaction_apprenants.views._local_analysis_class_counts", return_value={"cla001": 2})
    def test_build_satisfaction_dashboard_data_uses_missing_analysis_totals_for_prestation_count(
        self,
        _mock_class_counts,
        _mock_base_queryset,
        mock_dashboard_row_from_answer,
        mock_thresholded_dashboard_rows,
        _mock_terminated,
        _mock_threshold_codes,
        _mock_qualified,
        _mock_source_options,
        _mock_source_index,
        _mock_attach_network_rows,
        _mock_assign_enquete_ids,
        _mock_filter_options,
        _mock_class_filter_options,
        _mock_active_filter_summary,
        _mock_missing_analysis,
        _mock_table_details,
    ):
        row = {
            "fenetre": "2",
            "prestation_code": "PRESTA001",
            "prestataire": "Prestataire A",
            "beneficiaire": "Beneficiaire A",
            "classe_code": "CLA001",
            "formation_intitule": "Formation A",
            "classe_intitule": "Formation A",
            "cohorte": "1",
            "ville": "Garoua",
            "user": "agent-a",
            "modified_at": 1,
            "q1_clarte_exposes": 5,
            "q2_interaction_formateur": 4,
            "q3_maitrise_contenu": 4,
            "q4_salle_adequate": 5,
            "q5_materiel_disponible": 4,
            "q6_organisation_temps": 5,
            "q7_utilite_formation": 4,
            "q8_adequation_besoins": 5,
            "q9_satisfaction_globale": 5,
        }
        mock_dashboard_row_from_answer.return_value = row
        mock_thresholded_dashboard_rows.return_value = (
            [row],
            [
                {
                    "code": "CLA001",
                    "intitule": "Formation A",
                    "prestation": "PRESTA001",
                    "cohorte": "1",
                    "nb": 1,
                    "avgs": [4.56] * 9,
                    "total_apprenants": 2,
                    "threshold_reached": True,
                }
            ],
        )

        request = SimpleNamespace(GET=QueryDict("prestataire=Prestataire+A", mutable=True))

        dashboard = _build_satisfaction_dashboard_data(request)

        self.assertEqual(dashboard["context"]["analyzed_prestations_count"], 47)
        self.assertEqual(dashboard["context"]["analyzed_prestations_total_count"], 75)
        self.assertEqual(dashboard["context"]["analyzed_prestations_ratio"], "47/75")
        _mock_source_index.assert_called_once_with(source_key="cutoff")


class SatisfactionMissingPrestationsAnalysisTests(TestCase):
    def test_missing_analysis_ignores_non_callable_classes_for_category(self):
        Appel.objects.create(
            code="APP-CLA001",
            nom="Sans numero",
            classe_label="CLA001",
            fenetre="2",
            is_active=True,
        )
        Appel.objects.create(
            code="APP-CLA002",
            nom="Joignable",
            classe_label="CLA002",
            telephone1="690001122",
            fenetre="2",
            is_active=True,
        )

        analysis = _build_missing_prestations_analysis(
            {"presta001"},
            set(),
            {
                "classes": {
                    "cla001": {
                        "classe_id": "CLA001",
                        "prestation_id": "PRESTA001",
                        "statut_prestation": "TERMINE",
                    },
                    "cla002": {
                        "classe_id": "CLA002",
                        "prestation_id": "PRESTA001",
                        "statut_prestation": "TERMINE",
                    },
                },
                "records": {
                    "app-cla001": {
                        "classe_id": "CLA001",
                        "prestation_id": "PRESTA001",
                        "telephone1": "",
                        "telephone2": "",
                    },
                    "app-cla002": {
                        "classe_id": "CLA002",
                        "prestation_id": "PRESTA001",
                        "telephone1": "690001122",
                        "telephone2": "",
                    },
                },
                "prestations": {
                    "presta001": {
                        "prestation_id": "PRESTA001",
                        "prestataire": "Prestataire A",
                        "beneficiaire": "Beneficiaire A",
                        "formation": "Formation A",
                    }
                },
            },
            [],
            {},
        )

        self.assertEqual(analysis["by_category"]["pas_de_numero"], 0)
        self.assertEqual(analysis["details"][0]["category"], "pas_seuil_atteint")


@override_settings(ROOT_URLCONF="App_PADESCE.urls")
class SatisfactionGeneralPageTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="padesce-general-analysis-")
        self.override = override_settings(
            ANALYSIS_MANUAL_EXCLUSIONS_FILE=str(
                Path(self.temp_dir) / "manual-analysis-exclusions.json"
            )
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="general-manager",
            password="test-pass-123",
        )
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        self.user.groups.add(manager_group)
        self.client.force_login(self.user)

        self.prestataire = Prestataire.objects.create(
            code="PREST-A",
            raison_sociale="Prestataire A",
        )
        self.beneficiaire = Beneficiaire.objects.create(nom_structure="Beneficiaire A")
        self.formation = Formation.objects.create(
            code="FORM-A",
            nom="Formation A",
            fenetre="2",
            statut="termine",
        )
        self.prestation = Prestation.objects.create(
            code="PRESTA001",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
        )
        self.lieu = Lieu.objects.create(code="LIEU001", nom_lieu="Lieu Test", ville="Garoua")
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Formation A",
            fenetre="2",
            statut="termine",
        )

        self.eligible_appel = Appel.objects.create(
            code="APP100",
            nom="Amina Analyse",
            classe_label="CLA001",
            classe=self.classe,
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            telephone1="690001100",
            fenetre="2",
            status="termine",
            is_active=True,
        )
        AppelAnswers.objects.create(
            appel=self.eligible_appel,
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
            recommandations="Suivi",
            modified_by=self.user,
        )

        self.no_phone_appel = Appel.objects.create(
            code="APP101",
            nom="Binta Sans Numero",
            classe_label="CLA001",
            classe=self.classe,
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            status="termine",
            is_active=True,
        )
        AppelAnswers.objects.create(
            appel=self.no_phone_appel,
            q1_clarte_exposes=3,
            q2_interaction_formateur=3,
            q3_maitrise_contenu=3,
            q4_salle_adequate=3,
            q5_materiel_disponible=3,
            q6_organisation_temps=3,
            q7_utilite_formation=3,
            q8_adequation_besoins=3,
            q9_satisfaction_globale=3,
            commentaire="Tout a 3",
            recommandations="Verifier numero",
            modified_by=self.user,
        )

        self.eligible_apprenant = Apprenant.objects.create(
            code="APP100",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Amina Analyse",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            prestataire="Prestataire A",
            telephone1="690001100",
        )
        self.no_phone_apprenant = Apprenant.objects.create(
            code="APP101",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Binta Sans Numero",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            prestataire="Prestataire A",
        )
        self.termine_without_form_appel = Appel.objects.create(
            code="APP102",
            nom="Celia Sans Formulaire",
            classe_label="CLA001",
            classe=self.classe,
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            telephone1="690001102",
            fenetre="2",
            status="termine",
            is_active=True,
        )
        self.termine_without_form_apprenant = Apprenant.objects.create(
            code="APP102",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Celia Sans Formulaire",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            prestataire="Prestataire A",
            telephone1="690001102",
        )
        self.formulaire_non_termine_appel = Appel.objects.create(
            code="APP103",
            nom="David Statut A Corriger",
            classe_label="CLA001",
            classe=self.classe,
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            telephone1="690001103",
            fenetre="2",
            status="formulaire_rempli",
            is_active=True,
        )
        AppelAnswers.objects.create(
            appel=self.formulaire_non_termine_appel,
            q1_clarte_exposes=5,
            q2_interaction_formateur=5,
            q3_maitrise_contenu=4,
            q4_salle_adequate=4,
            q5_materiel_disponible=4,
            q6_organisation_temps=4,
            q7_utilite_formation=5,
            q8_adequation_besoins=5,
            q9_satisfaction_globale=5,
            commentaire="Formulaire deja rempli",
            recommandations="Passer en termine",
            modified_by=self.user,
        )
        self.formulaire_non_termine_apprenant = Apprenant.objects.create(
            code="APP103",
            classe=self.classe,
            formation=self.formation,
            nom_complet="David Statut A Corriger",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            prestataire="Prestataire A",
            telephone1="690001103",
        )
        self.fallback_lookup_appel = Appel.objects.create(
            code="CALL104",
            nom="Fatou Fallback",
            classe_label="CLA001",
            classe=self.classe,
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            telephone1="690001104",
            fenetre="2",
            status="termine",
            is_active=True,
        )
        self.fallback_lookup_apprenant = Apprenant.objects.create(
            code="APP104",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Fatou Fallback",
            beneficiaire="Beneficiaire A",
            fenetre="2",
            prestataire="Prestataire A",
            telephone1="690001104",
        )

    @patch("App_PADESCE.satisfaction_apprenants.views.get_workbook_source_options")
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index")
    @patch("App_PADESCE.satisfaction_apprenants.views._general_analysis_threshold_codes")
    def test_general_page_displays_analysis_state_and_filters(
        self,
        mock_threshold_codes,
        mock_source_index,
        mock_source_options,
    ):
        mock_threshold_codes.return_value = {"cla001"}
        mock_source_options.return_value = [{"value": "", "label": "Principal"}]
        mock_source_index.return_value = {
            "records": {
                "app100": {
                    "apprenant_id": "NET001",
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA001",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "fenetre": "2",
                },
                "app101": {
                    "apprenant_id": "NET002",
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA001",
                    "prestataire": "Prestataire A",
                    "beneficiaire": "Beneficiaire A",
                    "fenetre": "2",
                },
            }
        }

        response = self.client.get(reverse("satisfaction_general_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NET001")
        self.assertContains(response, "Pris en compte")
        self.assertContains(response, "Sans numero")
        self.assertContains(response, "Masquer la selection")

        filtered_response = self.client.get(
            reverse("satisfaction_general_page"),
            {"without_phone": "1", "all_three": "1"},
        )

        self.assertEqual(filtered_response.status_code, 200)
        self.assertContains(filtered_response, "NET002")
        self.assertNotContains(filtered_response, "NET001")

    @patch("App_PADESCE.satisfaction_apprenants.views.get_workbook_source_options", return_value=[])
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index", return_value={"records": {}})
    @patch("App_PADESCE.satisfaction_apprenants.views._general_analysis_threshold_codes", return_value=set())
    def test_general_toggle_exclusion_updates_appel_flag(
        self,
        _mock_threshold_codes,
        _mock_source_index,
        _mock_source_options,
    ):
        response = self.client.post(
            reverse("satisfaction_general_toggle_exclusion"),
            {
                "appel_id": self.eligible_appel.pk,
                "next": reverse("satisfaction_general_page"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("satisfaction_general_page"))
        self.eligible_appel.refresh_from_db()
        self.assertTrue(appel_is_manually_excluded(self.eligible_appel))

    @patch("App_PADESCE.satisfaction_apprenants.views.get_workbook_source_options", return_value=[])
    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index", return_value={"records": {}})
    @patch("App_PADESCE.satisfaction_apprenants.views._general_analysis_threshold_codes", return_value=set())
    def test_general_bulk_exclusion_updates_selected_appels(
        self,
        _mock_threshold_codes,
        _mock_source_index,
        _mock_source_options,
    ):
        response = self.client.post(
            reverse("satisfaction_general_toggle_exclusion"),
            {
                "appel_ids": [self.eligible_appel.pk, self.no_phone_appel.pk],
                "action": "exclude",
                "next": reverse("satisfaction_general_page"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("satisfaction_general_page"))
        self.eligible_appel.refresh_from_db()
        self.no_phone_appel.refresh_from_db()
        self.assertTrue(appel_is_manually_excluded(self.eligible_appel))
        self.assertTrue(appel_is_manually_excluded(self.no_phone_appel))

    def test_update_form_page_is_available(self):
        response = self.client.get(reverse("satisfaction_update_form_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UPDATE FORM")
        self.assertContains(response, "[APP100, APP101]")
        self.assertContains(response, "Termine Sans Formulaire")
        self.assertContains(response, "Formulaire Present / Statut Non Termine")
        self.assertContains(response, "APP102")
        self.assertContains(response, "APP103")
        self.assertContains(response, "CALL104")

    def test_update_form_page_updates_batch_codes_in_declared_order(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "classe_code": "CLA001",
                "codes_text": "[APP100, APP101]",
                "q1_clarte_exposes": "[5,4]",
                "q2_interaction_formateur": "5",
                "q3_maitrise_contenu": "5",
                "q4_salle_adequate": "5",
                "q5_materiel_disponible": "5",
                "q6_organisation_temps": "5",
                "q7_utilite_formation": "5",
                "q8_adequation_besoins": "5",
                "q9_satisfaction_globale": "[4,5]",
                "commentaire_values": "[Commentaire A, Commentaire B]",
                "recommandations_values": "[Reco A, Reco B]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 formulaire(s) mis a jour.")
        self.assertContains(response, "Formulaire mis a jour et fiche satisfaction synchronisee.")

        answers_one = AppelAnswers.objects.get(appel=self.eligible_appel)
        answers_two = AppelAnswers.objects.get(appel=self.no_phone_appel)
        self.assertEqual(answers_one.q1_clarte_exposes, 5)
        self.assertEqual(answers_two.q1_clarte_exposes, 4)
        self.assertEqual(answers_one.q9_satisfaction_globale, 4)
        self.assertEqual(answers_two.q9_satisfaction_globale, 5)
        self.assertEqual(answers_one.commentaire, "Commentaire A")
        self.assertEqual(answers_two.commentaire, "Commentaire B")
        self.assertEqual(answers_one.recommandations, "Reco A")
        self.assertEqual(answers_two.recommandations, "Reco B")
        self.assertEqual(answers_one.modified_by, self.user)

        self.eligible_appel.refresh_from_db()
        self.no_phone_appel.refresh_from_db()
        self.assertEqual(self.eligible_appel.status, "formulaire_rempli")
        self.assertEqual(self.no_phone_appel.status, "formulaire_rempli")

        survey_one = SatisfactionApprenant.objects.get(appel=self.eligible_appel)
        survey_two = SatisfactionApprenant.objects.get(appel=self.no_phone_appel)
        self.assertEqual(survey_one.apprenant, self.eligible_apprenant)
        self.assertEqual(survey_two.apprenant, self.no_phone_apprenant)
        self.assertEqual(survey_one.classe, self.classe)
        self.assertEqual(survey_two.classe, self.classe)
        self.assertEqual(survey_one.q1_clarte_exposes, 5)
        self.assertEqual(survey_two.q1_clarte_exposes, 4)
        self.assertEqual(survey_one.commentaire, "Commentaire A")
        self.assertEqual(survey_two.recommandations, "Reco B")

    def test_update_form_page_rejects_mismatched_class(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "codes_text": "APP100|CLA999",
                "q1_clarte_exposes": "5",
                "commentaire_values": "Commentaire force",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Classe attendue CLA999 differente de la classe trouvee CLA001.")

        self.eligible_appel.refresh_from_db()
        answers = AppelAnswers.objects.get(appel=self.eligible_appel)
        self.assertEqual(self.eligible_appel.status, "termine")
        self.assertEqual(answers.q1_clarte_exposes, 4)
        self.assertEqual(answers.commentaire, "RAS")
        self.assertFalse(SatisfactionApprenant.objects.filter(appel=self.eligible_appel).exists())

    def test_update_form_page_applies_default_values_when_fields_are_blank(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "classe_code": "CLA001",
                "codes_text": "[APP100, APP101]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2 formulaire(s) mis a jour.")

        answers_one = AppelAnswers.objects.get(appel=self.eligible_appel)
        answers_two = AppelAnswers.objects.get(appel=self.no_phone_appel)
        for answer in (answers_one, answers_two):
            self.assertEqual(answer.q1_clarte_exposes, 3)
            self.assertEqual(answer.q2_interaction_formateur, 3)
            self.assertEqual(answer.q3_maitrise_contenu, 3)
            self.assertEqual(answer.q4_salle_adequate, 3)
            self.assertEqual(answer.q5_materiel_disponible, 3)
            self.assertEqual(answer.q6_organisation_temps, 3)
            self.assertEqual(answer.q7_utilite_formation, 3)
            self.assertEqual(answer.q8_adequation_besoins, 3)
            self.assertEqual(answer.q9_satisfaction_globale, 3)
            self.assertEqual(answer.commentaire, "RAS")
            self.assertEqual(answer.recommandations, "RAS")

        self.eligible_appel.refresh_from_db()
        self.no_phone_appel.refresh_from_db()
        self.assertEqual(self.eligible_appel.status, "formulaire_rempli")
        self.assertEqual(self.no_phone_appel.status, "formulaire_rempli")

    def test_update_form_page_updates_selected_termine_without_form_rows(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "selected_targets": [f"{self.termine_without_form_appel.code}|CLA001"],
                "action": "update_form",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 formulaire(s) mis a jour.")

        answers = AppelAnswers.objects.get(appel=self.termine_without_form_appel)
        self.assertEqual(answers.q1_clarte_exposes, 3)
        self.assertEqual(answers.q9_satisfaction_globale, 3)
        self.assertEqual(answers.commentaire, "RAS")
        self.assertEqual(answers.recommandations, "RAS")

        self.termine_without_form_appel.refresh_from_db()
        self.assertEqual(self.termine_without_form_appel.status, "formulaire_rempli")
        survey = SatisfactionApprenant.objects.get(appel=self.termine_without_form_appel)
        self.assertEqual(survey.apprenant, self.termine_without_form_apprenant)
        self.assertEqual(survey.classe, self.classe)

    def test_update_form_page_changes_status_for_rows_with_existing_form(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "selected_targets": [f"{self.formulaire_non_termine_appel.code}|CLA001"],
                "target_status": "termine",
                "action": "update_status",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 statut(s) mis a jour.")
        self.assertContains(response, "Statut mis a jour vers Termine.")

        self.formulaire_non_termine_appel.refresh_from_db()
        self.assertEqual(self.formulaire_non_termine_appel.status, "termine")
        answers = AppelAnswers.objects.get(appel=self.formulaire_non_termine_appel)
        self.assertEqual(answers.commentaire, "Formulaire deja rempli")
        self.assertEqual(answers.recommandations, "Passer en termine")

    def test_update_form_page_requires_target_status_for_status_action(self):
        response = self.client.post(
            reverse("satisfaction_update_form_page"),
            {
                "selected_targets": [f"{self.formulaire_non_termine_appel.code}|CLA001"],
                "action": "update_status",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Statut a appliquer: Choisissez le statut a appliquer.")

        self.formulaire_non_termine_appel.refresh_from_db()
        self.assertEqual(self.formulaire_non_termine_appel.status, "formulaire_rempli")


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


class MissingLearnerImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_superuser(
            username="superadmin",
            email="superadmin@example.com",
            password="testpass123",
        )

    @patch("App_PADESCE.satisfaction_apprenants.views.build_padesce_source_index", return_value={"classes": {}})
    @patch("App_PADESCE.satisfaction_apprenants.views.build_consolidation_call_candidates")
    def test_import_missing_apprenants_shortens_oversized_codes_and_skips_reimports(
        self,
        mock_build_consolidation,
        _mock_build_source_index,
    ):
        raw_code = "9" * 81
        record = {
            "row_number": 1745,
            "numero": "1744",
            "code": raw_code,
            "nom": "BOUSATA Martha",
            "prestataire": "CFEM",
            "beneficiaire": "IRISA",
            "lieu": "Gueme",
            "classe_label": "CLA069",
            "fenetre": "3",
            "telephone1": "699112233",
            "formation": "Itineraire technique de bonne production du riz",
            "prestation_id": "PRESTA066",
        }
        mock_build_consolidation.return_value = {"records": [record]}
        expected_code = _safe_import_appel_code(record)

        self.client.force_login(self.user)
        url = reverse("import_missing_apprenants") + "?source=cutoff"
        payload = json.dumps({"offset": 0, "prestation_ids": ["PRESTA066"]})

        response = self.client.post(url, data=payload, content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["imported"], 1)
        self.assertEqual(Appel.objects.count(), 1)
        appel = Appel.objects.get()
        self.assertEqual(appel.code, expected_code)
        self.assertNotEqual(appel.code, raw_code)
        self.assertLessEqual(len(appel.code), Appel._meta.get_field("code").max_length)

        second_response = self.client.post(url, data=payload, content_type="application/json")

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["imported"], 0)
        self.assertEqual(Appel.objects.count(), 1)


class PrestationRankingServiceTests(TestCase):
    def test_get_prestations_ranking_uses_fixed_query_count(self):
        beneficiaire = Beneficiaire.objects.create(nom_structure="Beneficiaire Nord", region="Nord")
        prestataire = Prestataire.objects.create(code="P001", raison_sociale="Prestataire Alpha")
        formation = Formation.objects.create(code="F001", nom="Formation X")
        Prestation.objects.create(
            code="PRESTA001",
            prestataire=prestataire,
            formation=formation,
            beneficiaire=beneficiaire,
            effectif_a_former=20,
            actif=True,
        )

        prestation_stats = [
            {
                "code": "PRESTA001",
                "prestataire": "Prestataire Alpha",
                "beneficiaire": "Beneficiaire Nord",
                "nb": 10,
                "avg": 4.0,
            },
            {
                "code": "PRESTA999",
                "prestataire": "Prestataire Beta",
                "beneficiaire": "Beneficiaire Nord",
                "nb": 2,
                "avg": 5.0,
            },
        ]

        with self.assertNumQueries(2):
            ranking = get_prestations_ranking(prestation_stats, order="desc")

        ranking_by_code = {item["code"]: item for item in ranking}
        self.assertEqual(ranking_by_code["PRESTA001"]["effectif"], 20)
        self.assertEqual(ranking_by_code["PRESTA001"]["region"], "Nord")
        self.assertEqual(ranking_by_code["PRESTA999"]["effectif"], 2)
        self.assertEqual(ranking_by_code["PRESTA999"]["region"], "Nord")
