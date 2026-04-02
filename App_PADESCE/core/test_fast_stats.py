from datetime import date

from django.test import TestCase

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.core.fast_stats import (
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
        self.prestataire = Prestataire.objects.create(
            code="PST001",
            raison_sociale="Prestataire Alpha",
        )
        self.beneficiaire = Beneficiaire.objects.create(
            nom_structure="Beneficiaire Beta",
            ville="Garoua",
        )
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
        self.lieu = Lieu.objects.create(
            code="LIE001",
            nom_lieu="Centre Garoua",
            ville="Garoua",
        )
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

    def test_build_fast_stats_bundle_returns_apprenant_and_formateur_rows(self):
        bundle = build_fast_stats_bundle(request_like_with_query("prestataire=Prestataire+Alpha"))

        apprenant_mode = self._mode(bundle, "apprenant")
        formateur_mode = self._mode(bundle, "formateur")

        self.assertEqual(apprenant_mode["class_count"], 1)
        self.assertEqual(formateur_mode["class_count"], 1)

        apprenant_row = apprenant_mode["rows"][0]
        self.assertEqual(apprenant_row["prestation_label"], "PRESTA001")
        self.assertEqual(apprenant_row["classe_code"], "CLA011")
        self.assertEqual(apprenant_row["summary_label"], "1 réponse(s) · 2 appel(s)")
        self.assertEqual(apprenant_row["left_primary_name"], "Amina Apprenante")
        self.assertEqual(apprenant_row["left_primary_phone"], "690000001")
        self.assertEqual(apprenant_row["right_primary_name"], "Amina Apprenante")
        self.assertEqual(apprenant_row["right_primary_phone"], "690000001")

        formateur_row = formateur_mode["rows"][0]
        self.assertEqual(formateur_row["summary_label"], "1 terminé(s) · 2 contact(s)")
        self.assertEqual(formateur_row["left_primary_name"], "Formateur Principal")
        self.assertEqual(formateur_row["left_primary_phone"], "699100100")
        self.assertEqual(formateur_row["left_secondary_name"], "Contact classe 1")
        self.assertEqual(formateur_row["left_secondary_phone"], "677200200")
        self.assertEqual(formateur_row["right_primary_name"], "Contact terminé 1")
        self.assertEqual(formateur_row["right_primary_phone"], "699100100")
        self.assertEqual(formateur_row["right_secondary_name"], "Contact terminé 2")
        self.assertEqual(formateur_row["right_secondary_phone"], "677200200")

    def test_build_fast_stats_workbook_creates_both_sheets_with_expected_headers(self):
        workbook = build_fast_stats_workbook(
            request_like_with_query("prestataire=Prestataire+Alpha"),
            active_mode="formateur",
        )

        self.assertEqual(
            workbook.sheetnames,
            ["FAST STATS APPRENANTS", "FAST STATS FORMATEURS"],
        )
        self.assertEqual(workbook.active.title, "FAST STATS FORMATEURS")

        apprenant_sheet = workbook["FAST STATS APPRENANTS"]
        formateur_sheet = workbook["FAST STATS FORMATEURS"]

        self.assertEqual(apprenant_sheet["E1"].value, "Source plateforme apprenants")
        self.assertEqual(apprenant_sheet["I1"].value, "Source appels apprenants")
        self.assertEqual(apprenant_sheet["A3"].value, "PRESTA001")
        self.assertEqual(apprenant_sheet["B3"].value, "CLA011")
        self.assertEqual(apprenant_sheet["D3"].value, "1 réponse(s) · 2 appel(s)")

        self.assertEqual(formateur_sheet["E1"].value, "Source classes / apprenants")
        self.assertEqual(formateur_sheet["I1"].value, "Source appels formateurs")
        self.assertEqual(formateur_sheet["B3"].value, "CLA011")
        self.assertEqual(formateur_sheet["F3"].value, "699100100")
        self.assertEqual(formateur_sheet["J3"].value, "699100100")
