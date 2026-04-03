from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.fast_stats import (
    build_fast_stats_api_payload,
    build_fast_stats_bundle,
    build_fast_stats_workbook,
    request_like_with_query,
)
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formation,
    Formateur,
    Lieu,
    Prestataire,
    Prestation,
)


class FastStatsTests(TestCase):
    def setUp(self):
        self.source_index_patcher = patch("App_PADESCE.core.fast_stats.build_padesce_source_index")
        self.mock_build_padesce_source_index = self.source_index_patcher.start()
        self.addCleanup(self.source_index_patcher.stop)
        self.mock_build_padesce_source_index.return_value = {"records": {}}

        self.user = get_user_model().objects.create_user(
            username="fast-stats-admin",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )
        self.prestataire = Prestataire.objects.create(code="PST001", raison_sociale="Prestataire Alpha")
        self.beneficiaire = Beneficiaire.objects.create(nom_structure="Beneficiaire Beta", ville="Garoua")
        self.formation = Formation.objects.create(
            code="FOR001",
            nom="Transformation digitale",
            fenetre="2",
            statut="termine",
        )
        self.prestation = Prestation.objects.create(
            code="PRESTA001",
            prestataire=self.prestataire,
            beneficiaire=self.beneficiaire,
            formation=self.formation,
            effectif_a_former=25,
        )
        self.lieu = Lieu.objects.create(code="LIE001", nom_lieu="Centre Garoua", ville="Garoua")
        self.formateur = Formateur.objects.create(
            code="FMT001",
            nom_complet="Formateur Principal",
            telephone="699100100",
            fenetre="2",
        )
        self.classe = Classe.objects.create(
            code="CLA011",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Transformation digitale",
            formateur=self.formateur,
            fenetre="2",
            cohorte=1,
            statut="termine",
        )
        Apprenant.objects.create(
            code="APP001",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Amina Apprenante",
            telephone1="690000001",
            tel_formateur="699100100",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            fenetre="2",
            cohorte="1",
        )
        Apprenant.objects.create(
            code="APP002",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Brice Apprenant",
            telephone1="690000002",
            tel_formateur="677200200",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            fenetre="2",
            cohorte="1",
        )
        appel_termine = Appel.objects.create(
            code="CALL001",
            nom="Amina Apprenante",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            classe=self.classe,
            telephone1="690000001",
            status="termine",
            is_active=True,
        )
        AppelAnswers.objects.create(
            appel=appel_termine,
            q1_clarte_exposes=5,
            q2_interaction_formateur=4,
            q3_maitrise_contenu=4,
            q4_salle_adequate=5,
            q5_materiel_disponible=4,
            q6_organisation_temps=4,
            q7_utilite_formation=5,
            q8_adequation_besoins=4,
            q9_satisfaction_globale=5,
        )
        Appel.objects.create(
            code="CALL002",
            nom="Brice Apprenant",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            classe=self.classe,
            telephone1="690000002",
            status="en_cours",
            is_active=True,
        )
        AppelFormateur.objects.create(
            reference_code="F-CALL-001",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            formation=self.classe.intitule_formation,
            lieu=self.lieu.nom_lieu,
            telephone="699100100",
            cohorte="1",
            session_date=date(2026, 4, 1),
            source_contact="699100100/677200200",
            is_active=True,
            status="termine",
            q1_prerequis_apprenants=4,
        )

    def _mode(self, bundle, mode_id):
        return next(mode for mode in bundle["modes"] if mode["id"] == mode_id)

    def test_build_fast_stats_bundle_matches_new_excel_structures(self):
        bundle = build_fast_stats_bundle(request_like_with_query("prestataire=Prestataire+Alpha"))

        apprenant_mode = self._mode(bundle, "apprenant")
        formateur_mode = self._mode(bundle, "formateur")

        self.assertEqual(apprenant_mode["sheet_name"], "Enquête de satisfaction")
        self.assertEqual(formateur_mode["sheet_name"], "Enquête de formateur")

        apprenant_row = apprenant_mode["rows"][0]
        self.assertEqual(apprenant_row["index"], 1)
        self.assertEqual(apprenant_row["prestation_id"], "PRESTA001")
        self.assertEqual(apprenant_row["classe_id"], "CLA011")
        self.assertEqual(apprenant_row["apprenant_count"], 2)
        self.assertEqual(apprenant_row["calls_effectues"], 2)
        self.assertEqual(apprenant_row["calls_termines"], 1)
        self.assertEqual(apprenant_row["pct_appel_effectue_label"], "100.00%")
        self.assertEqual(apprenant_row["pct_appel_termine_label"], "50.00%")
        self.assertEqual(apprenant_row["pct_enquetes_label"], "50.00%")

        formateur_row = formateur_mode["rows"][0]
        self.assertEqual(formateur_row["class_link_url"], "https://testserver/classe/CLA011/")
        self.assertEqual(formateur_row["beneficiaire_name"], "Beneficiaire Beta")
        self.assertEqual(formateur_row["prestataire_name"], "Prestataire Alpha")
        self.assertEqual(formateur_row["calendar_contacts"][0]["name"], "Formateur Principal")
        self.assertEqual(formateur_row["calendar_contacts"][0]["phone"], "699100100")
        self.assertEqual(formateur_row["calendar_contacts"][1]["name"], "Contact calendrier N2")
        self.assertEqual(formateur_row["calendar_contacts"][1]["phone"], "677200200")
        self.assertEqual(formateur_row["descente_contacts"][0]["name"], "Formateur Principal")
        self.assertEqual(formateur_row["descente_contacts"][0]["phone"], "699100100")
        self.assertEqual(formateur_row["descente_contacts"][1]["name"], "Contact calendrier N2")
        self.assertEqual(formateur_row["descente_contacts"][1]["phone"], "677200200")

    def test_build_fast_stats_workbook_writes_expected_sheets_and_cells(self):
        workbook = build_fast_stats_workbook(
            request_like_with_query("prestataire=Prestataire+Alpha"),
            active_mode="formateur",
        )

        self.assertIn("Enquête de satisfaction", workbook.sheetnames)
        self.assertIn("Enquête de formateur", workbook.sheetnames)
        self.assertEqual(workbook.active.title, "Enquête de formateur")

        apprenant_sheet = workbook["Enquête de satisfaction"]
        formateur_sheet = workbook["Enquête de formateur"]

        self.assertEqual(apprenant_sheet["B1"].value, "Total classe de la prestation termine")
        self.assertEqual(apprenant_sheet["B4"].value, "PRESTA001")
        self.assertEqual(apprenant_sheet["C4"].value, "CLA011")
        self.assertEqual(apprenant_sheet["D4"].value, 2)
        self.assertEqual(apprenant_sheet["F4"].value, 1)

        self.assertEqual(formateur_sheet["B4"].value, "PRESTA001")
        self.assertEqual(formateur_sheet["C4"].value, "CLA011")
        self.assertEqual(formateur_sheet["D4"].value, "Ouvrir CLA011")
        self.assertEqual(formateur_sheet["E4"].value, "Beneficiaire Beta")
        self.assertEqual(formateur_sheet["G4"].value, "Formateur Principal")
        self.assertEqual(formateur_sheet["H4"].value, "699100100")
        self.assertEqual(formateur_sheet["K4"].value, "Formateur Principal")
        self.assertEqual(formateur_sheet["L4"].value, "699100100")

    def test_fast_stats_api_returns_json_payload(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("fast_stats_api"), {"prestataire": "Prestataire Alpha"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["prestataire"], "Prestataire Alpha")
        self.assertTrue(payload["terminated_only"])
        self.assertEqual(self._mode(payload, "apprenant")["rows"][0]["classe_id"], "CLA011")
        self.assertEqual(self._mode(payload, "formateur")["rows"][0]["class_link_url"], "http://testserver/classe/CLA011/")

    def test_build_fast_stats_api_payload_matches_bundle_shape(self):
        payload = build_fast_stats_api_payload(request_like_with_query("prestation=PRESTA001"))

        self.assertEqual(payload["filters"]["prestation"], "PRESTA001")
        self.assertEqual(len(payload["modes"]), 2)
        self.assertEqual(self._mode(payload, "apprenant")["row_count"], 1)

    def test_fast_stats_filters_match_fuzzy_prestataire_and_beneficiaire_labels(self):
        payload = build_fast_stats_api_payload(
            request_like_with_query("prestataire=prestataire+alpha&beneficiaire=beneficiaire")
        )

        self.assertEqual(self._mode(payload, "apprenant")["row_count"], 1)
        self.assertEqual(self._mode(payload, "formateur")["row_count"], 1)

    def test_fast_stats_uses_total_consolidated_class_size_for_apprenant_count(
        self,
    ):
        self.mock_build_padesce_source_index.reset_mock()
        self.mock_build_padesce_source_index.return_value = {
            "records": {
                "app001": {"classe_id": "CLA011", "telephone1": "690000001"},
                "app002": {"classe_id": "CLA011", "telephone1": ""},
                "app003": {"classe_id": "CLA011", "telephone1": ""},
            }
        }

        payload = build_fast_stats_api_payload(
            request_like_with_query("prestataire=Prestataire+Alpha&source=cutoff")
        )

        apprenant_row = self._mode(payload, "apprenant")["rows"][0]
        self.assertEqual(apprenant_row["apprenant_count"], 3)
        self.assertEqual(apprenant_row["calls_effectues"], 2)
        self.assertEqual(apprenant_row["calls_termines"], 1)
        self.assertEqual(apprenant_row["pct_appel_effectue_label"], "66.67%")
        self.assertEqual(apprenant_row["pct_appel_termine_label"], "50.00%")
        self.assertEqual(apprenant_row["pct_enquetes_label"], "33.33%")
        self.mock_build_padesce_source_index.assert_called_once_with(source_key="cutoff")
