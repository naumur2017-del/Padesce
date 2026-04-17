from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formateur,
    Formation,
    Prestataire,
    Prestation,
)
from App_PADESCE.satisfaction_apprenants.views import _build_prestation_indicators_table
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur
from App_PADESCE.satisfaction_formateurs.views import (
    _average_displayed_scores,
    _build_satisfaction_formateurs_dashboard_context,
)


class SatisfactionFormateurUpdateFormTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client.force_login(self.user)

        self.formateur = Formateur.objects.create(
            code="FOR001",
            nom_complet="Formateur Test",
            telephone="699000111",
        )
        self.formation = Formation.objects.create(
            code="FORM001",
            nom="Formation Test",
        )
        self.prestataire = Prestataire.objects.create(
            code="PRESTA001",
            raison_sociale="Prestataire Test",
        )
        self.beneficiaire = Beneficiaire.objects.create(
            nom_structure="Beneficiaire Test",
        )
        self.prestation = Prestation.objects.create(
            code="PRES001",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
        )
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            formation=self.formation,
            intitule_formation="Formation Test",
            formateur=self.formateur,
            cohorte=1,
        )

        self.terminee_sans_formulaire = AppelFormateur.objects.create(
            reference_code="FORM-001",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            formation=self.formation.nom,
            cohorte=str(self.classe.cohorte),
            telephone=self.formateur.telephone,
            session_date=date(2026, 4, 1),
            heure_debut="08:00",
            status="termine",
        )
        self.formulaire_present = AppelFormateur.objects.create(
            reference_code="FORM-002",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            formation=self.formation.nom,
            cohorte=str(self.classe.cohorte),
            telephone=self.formateur.telephone,
            session_date=date(2026, 4, 2),
            heure_debut="09:00",
            status="formulaire_rempli",
            q1_prerequis_apprenants=4,
            q2_interaction_apprenants=5,
            q3_competences_acquises=3,
            q4_gestion_administrative="RAS",
            q5_gestion_financiere="RAS",
            q6_communication="RAS",
            commentaires="RAS",
            recommandations="RAS",
        )

    def test_update_form_page_lists_trainer_candidates(self):
        response = self.client.get(reverse("satisfaction_formateurs_update_form_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UPDATE FORM FORMATEURS")
        self.assertContains(response, self.terminee_sans_formulaire.reference_code)
        self.assertContains(response, self.formulaire_present.reference_code)

    def test_batch_update_form_populates_scores_and_syncs_satisfaction(self):
        response = self.client.post(
            reverse("satisfaction_formateurs_update_form_page"),
            {
                "action": "update_form",
                "selected_targets": [self.terminee_sans_formulaire.reference_code],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.terminee_sans_formulaire.refresh_from_db()

        self.assertEqual(self.terminee_sans_formulaire.q1_prerequis_apprenants, 3)
        self.assertEqual(self.terminee_sans_formulaire.q2_interaction_apprenants, 3)
        self.assertEqual(self.terminee_sans_formulaire.q3_competences_acquises, 3)
        self.assertEqual(self.terminee_sans_formulaire.q4_gestion_administrative, "RAS")
        self.assertEqual(self.terminee_sans_formulaire.q5_gestion_financiere, "RAS")
        self.assertEqual(self.terminee_sans_formulaire.q6_communication, "RAS")
        self.assertEqual(self.terminee_sans_formulaire.commentaires, "RAS")
        self.assertEqual(self.terminee_sans_formulaire.recommandations, "RAS")
        self.assertEqual(self.terminee_sans_formulaire.status, "formulaire_rempli")

        survey = SatisfactionFormateur.objects.get(
            classe=self.classe,
            formateur=self.formateur,
            date=self.terminee_sans_formulaire.session_date,
        )
        self.assertEqual(survey.q1_prerequis_apprenants, 3)
        self.assertEqual(survey.q2_interaction_apprenants, 3)
        self.assertEqual(survey.q3_competences_acquises, 3)

    def test_batch_status_update_marks_call_complete(self):
        response = self.client.post(
            reverse("satisfaction_formateurs_update_form_page"),
            {
                "action": "update_status",
                "target_status": "termine",
                "selected_targets": [self.formulaire_present.reference_code],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.formulaire_present.refresh_from_db()

        self.assertEqual(self.formulaire_present.status, "termine")
        self.assertIsNotNone(self.formulaire_present.satisfaction_completed_at)
        self.assertTrue(
            SatisfactionFormateur.objects.filter(
                classe=self.classe,
                formateur=self.formateur,
                date=self.formulaire_present.session_date,
            ).exists()
        )


class SatisfactionFormateurDashboardAverageTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="testpass123",
        )
        self.client.force_login(self.user)
        self.factory = RequestFactory()
        completed_at_1 = timezone.make_aware(datetime(2026, 4, 10, 0, 0, 0))
        completed_at_2 = timezone.make_aware(datetime(2026, 4, 11, 0, 0, 0))

        AppelFormateur.objects.create(
            reference_code="AVG-001",
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            formation="Formation A",
            cohorte="1",
            telephone="699111111",
            session_date=date(2026, 4, 10),
            heure_debut="08:00",
            status="termine",
            q1_prerequis_apprenants=5,
            q2_interaction_apprenants=5,
            q3_competences_acquises=1,
            satisfaction_completed_at=completed_at_1,
        )
        AppelFormateur.objects.create(
            reference_code="AVG-002",
            prestataire="Prestataire A",
            beneficiaire="Beneficiaire A",
            formation="Formation A",
            cohorte="1",
            telephone="699222222",
            session_date=date(2026, 4, 11),
            heure_debut="09:00",
            status="termine",
            q1_prerequis_apprenants=1,
            q2_interaction_apprenants=1,
            q3_competences_acquises=None,
            satisfaction_completed_at=completed_at_2,
        )

    def test_global_average_is_computed_from_the_three_displayed_indicators(self):
        request = self.factory.get(reverse("satisfaction_formateurs_dashboard"))
        request.user = self.user
        context = _build_satisfaction_formateurs_dashboard_context(request)

        self.assertEqual(context["with_scores"], 1)
        self.assertEqual(list(context["global_avgs"].values()), [5.0, 5.0, 1.0])
        self.assertEqual(context["moyenne_generale_globale"], 3.67)

    def test_average_displayed_scores_matches_visible_q1_q3_values(self):
        self.assertEqual(_average_displayed_scores([2.98, 3.49, 3.12]), 3.20)

    def test_dashboard_context_normalizes_filter_options_with_null_like_values(self):
        AppelFormateur.objects.filter(reference_code="AVG-001").update(beneficiaire="   ")
        AppelFormateur.objects.create(
            reference_code="AVG-003",
            prestataire="Prestataire B",
            beneficiaire="",
            formation="Formation B",
            cohorte="",
            telephone="699333333",
            session_date=date(2026, 4, 12),
            heure_debut="10:00",
            status="en_attente",
        )

        request = self.factory.get(
            reverse("satisfaction_formateurs_dashboard"), {"tab": "beneficiaire"}
        )
        request.user = self.user
        context = _build_satisfaction_formateurs_dashboard_context(request)

        self.assertEqual(context["beneficiaires"], ["Beneficiaire A"])
        self.assertEqual(context["cohortes"], ["1"])


class PrestationIndicatorsFormateurMappingTests(TestCase):
    def setUp(self):
        self.formateur = Formateur.objects.create(
            code="FOR100",
            nom_complet="Formateur Indicateurs",
            telephone="699888777",
        )
        self.formation = Formation.objects.create(code="FORM100", nom="Formation Indicateurs")
        self.prestataire = Prestataire.objects.create(
            code="PTEST100",
            raison_sociale="Prestataire École",
        )
        self.beneficiaire = Beneficiaire.objects.create(nom_structure="Bénéficiaire Coop")
        self.prestation = Prestation.objects.create(
            code="PRESTA100",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
        )
        self.other_prestataire = Prestataire.objects.create(
            code="PTEST200",
            raison_sociale="Prestataire Autre",
        )
        self.other_beneficiaire = Beneficiaire.objects.create(nom_structure="Autre Bénéficiaire")
        self.other_prestation = Prestation.objects.create(
            code="PRESTA200",
            prestataire=self.other_prestataire,
            formation=self.formation,
            beneficiaire=self.other_beneficiaire,
        )
        Classe.objects.create(
            code="CLA100",
            prestation=self.prestation,
            formation=self.formation,
            intitule_formation="Formation Indicateurs",
            formateur=self.formateur,
            cohorte=1,
        )
        Classe.objects.create(
            code="CLA200",
            prestation=self.other_prestation,
            formation=self.formation,
            intitule_formation="Formation Indicateurs",
            formateur=self.formateur,
            cohorte=1,
        )

        AppelFormateur.objects.create(
            reference_code="IND-001",
            prestataire="prestataire ecole",
            beneficiaire="beneficiaire coop",
            formation=self.formation.nom,
            cohorte="1",
            telephone="699000001",
            session_date=date(2026, 4, 12),
            status="termine",
            q1_prerequis_apprenants=4,
            q2_interaction_apprenants=5,
            q3_competences_acquises=3,
            q4_gestion_administrative="RAS",
            q5_gestion_financiere="OK",
            q6_communication="Bien",
            satisfaction_completed_at=timezone.make_aware(datetime(2026, 4, 12, 10, 0, 0)),
        )
        AppelFormateur.objects.create(
            reference_code="IND-002",
            prestataire="Prestataire École",
            beneficiaire="Bénéficiaire Coop",
            formation=self.formation.nom,
            cohorte="1",
            telephone="699000002",
            session_date=date(2026, 4, 13),
            status="termine",
            q1_prerequis_apprenants=2,
            q2_interaction_apprenants=3,
            q3_competences_acquises=4,
            q4_gestion_administrative="RAS",
            q5_gestion_financiere="A suivre",
            q6_communication="Bien",
            satisfaction_completed_at=timezone.make_aware(datetime(2026, 4, 13, 11, 0, 0)),
        )
        AppelFormateur.objects.create(
            reference_code="IND-003",
            prestataire="Prestataire École",
            beneficiaire="Bénéficiaire Coop",
            formation=self.formation.nom,
            cohorte="1",
            telephone="699000003",
            session_date=date(2026, 4, 14),
            status="termine",
            q1_prerequis_apprenants=5,
            q2_interaction_apprenants=None,
            q3_competences_acquises=5,
        )

    def test_prestation_indicator_table_uses_formateur_combo_mapping(self):
        rows = _build_prestation_indicators_table()
        row_by_code = {row["code"]: row for row in rows}

        matched = row_by_code["PRESTA100"]["formateur"]
        self.assertEqual(matched["count"], 2)
        self.assertEqual(matched["q1_prerequis_apprenants"], 3.0)
        self.assertEqual(matched["q2_interaction_apprenants"], 4.0)
        self.assertEqual(matched["q3_competences_acquises"], 3.5)
        self.assertEqual(matched["q4_gestion_administrative"], ["RAS"])
        self.assertEqual(matched["q6_communication"], ["Bien"])

        unmatched = row_by_code["PRESTA200"]["formateur"]
        self.assertEqual(unmatched["count"], 0)
        self.assertIsNone(unmatched["q1_prerequis_apprenants"])
