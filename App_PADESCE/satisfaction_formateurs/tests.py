from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.appels.models import AppelFormateur
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formateur,
    Formation,
    Prestataire,
    Prestation,
)
from App_PADESCE.satisfaction_formateurs.models import SatisfactionFormateur


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
