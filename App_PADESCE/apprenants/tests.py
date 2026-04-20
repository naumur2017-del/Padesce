from datetime import date
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import RequestFactory, TestCase
from django.urls import reverse

from App_PADESCE.appels.models import Appel
from App_PADESCE.apprenants.models import Apprenant
from App_PADESCE.apprenants.views import redirect_to_analysis_detail
from App_PADESCE.formations.models import Beneficiaire, Classe, Formation, Prestataire, Prestation
from App_PADESCE.satisfaction_apprenants.models import SatisfactionApprenant


class ApprenantAnalysisShortcutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="shortcut-admin",
            password="test123",
            is_staff=True,
            is_superuser=True,
        )
        self.factory = RequestFactory()
        self.client.force_login(self.user)
        self.formation = Formation.objects.create(code="FORMA001", nom="Transformation")
        self.prestataire = Prestataire.objects.create(
            code="PSTA001",
            raison_sociale="Prestataire Test",
        )
        self.beneficiaire = Beneficiaire.objects.create(nom_structure="Beneficiaire Test")
        self.prestation = Prestation.objects.create(
            code="PRESTA001",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
        )
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            formation=self.formation,
            intitule_formation="Transformation",
        )

    def test_padesce_shortcut_redirects_to_analysis_form(self):
        apprenant = Apprenant.objects.create(
            code="APP1020",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Amina Test",
            telephone1="690000001",
        )
        appel = Appel.objects.create(
            code=apprenant.code,
            nom=apprenant.nom_complet,
            classe=self.classe,
            telephone1=apprenant.telephone1,
        )

        response = self.client.get(f"/padesce/apprenants/{apprenant.code}")

        expected_back_url = (
            f"{reverse('padesce:prestation_analysis_detail', args=[self.prestation.code])}"
            "?tab=apprenants"
        )
        expected_url = (
            f"{reverse('padesce:analysis_apprenant_call_detail', args=[appel.pk])}"
            f"?next={quote(expected_back_url, safe='')}#formulaire"
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_shortcut_prefers_explicit_satisfaction_link(self):
        apprenant = Apprenant.objects.create(
            code="APP2040",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Binta Test",
            telephone1="690000002",
        )
        appel = Appel.objects.create(
            code="CALL2040",
            nom=apprenant.nom_complet,
            classe=self.classe,
            telephone1=apprenant.telephone1,
        )
        SatisfactionApprenant.objects.create(
            appel=appel,
            classe=self.classe,
            apprenant=apprenant,
            date=date(2026, 4, 20),
            q1_clarte_exposes=5,
            q2_interaction_formateur=5,
            q3_maitrise_contenu=5,
            q4_salle_adequate=5,
            q5_materiel_disponible=5,
            q6_organisation_temps=5,
            q7_utilite_formation=5,
            q8_adequation_besoins=5,
            q9_satisfaction_globale=5,
        )

        response = self.client.get(reverse("padesce:apprenant_analysis_shortcut", args=[apprenant.code]))

        expected_back_url = (
            f"{reverse('padesce:prestation_analysis_detail', args=[self.prestation.code])}"
            "?tab=apprenants"
        )
        expected_url = (
            f"{reverse('padesce:analysis_apprenant_call_detail', args=[appel.pk])}"
            f"?next={quote(expected_back_url, safe='')}#formulaire"
        )
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_shortcut_returns_404_without_matching_active_call(self):
        apprenant = Apprenant.objects.create(
            code="APP9999",
            classe=self.classe,
            formation=self.formation,
            nom_complet="Sans Appel",
        )
        request = self.factory.get(f"/padesce/apprenants/{apprenant.code}/")
        request.user = self.user

        with self.assertRaises(Http404):
            redirect_to_analysis_detail(request, apprenant.code)
