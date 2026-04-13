import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from App_PADESCE.appels.models import Appel, AppelAnswers, AppelFormateur
from App_PADESCE.formations.models import (
    Beneficiaire,
    Classe,
    Formateur,
    Formation,
    Lieu,
    Prestataire,
    Prestation,
)


@override_settings(ROOT_URLCONF="App_PADESCE.urls")
class AnalysisEntityDetailTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="padesce-tests-media-")
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.media_root, ignore_errors=True))

        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="analysis-manager",
            password="test-pass-123",
        )
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        self.user.groups.add(manager_group)
        self.client.force_login(self.user)

        self.prestataire = Prestataire.objects.create(
            code="PST001",
            raison_sociale="Prestataire Alpha",
        )
        self.beneficiaire = Beneficiaire.objects.create(
            nom_structure="Beneficiaire Beta",
        )
        self.formation = Formation.objects.create(
            code="FOR001",
            nom="Transformation locale",
        )
        self.formateur = Formateur.objects.create(
            code="FMT001",
            nom_complet="Formateur Test",
            telephone="699001122",
        )
        self.lieu = Lieu.objects.create(
            code="LIE001",
            nom_lieu="Douala",
            ville="Douala",
        )
        self.prestation = Prestation.objects.create(
            code="PRESTA146",
            prestataire=self.prestataire,
            formation=self.formation,
            beneficiaire=self.beneficiaire,
            effectif_a_former=30,
            femmes=18,
        )
        self.classe = Classe.objects.create(
            code="CLA001",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Transformation locale",
            formateur=self.formateur,
            cohorte=1,
            statut="termine",
        )
        self.secondary_class = Classe.objects.create(
            code="CLA002",
            prestation=self.prestation,
            lieu=self.lieu,
            formation=self.formation,
            intitule_formation="Transformation locale - groupe 2",
            formateur=self.formateur,
            cohorte=2,
            statut="en_cours",
        )

        self.apprenant_call = Appel.objects.create(
            code="APP001",
            nom="Apprenant Analyse",
            classe=self.classe,
            classe_label=self.classe.code,
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            telephone1="677001122",
            status="termine",
            is_active=True,
            locked_by=self.user,
            audio_file=SimpleUploadedFile(
                "apprenant.mp3",
                b"fake-audio-apprenant",
                content_type="audio/mpeg",
            ),
        )
        AppelAnswers.objects.create(
            appel=self.apprenant_call,
            q1_clarte_exposes=4,
            q2_interaction_formateur=5,
            q3_maitrise_contenu=4,
            q4_salle_adequate=4,
            q5_materiel_disponible=4,
            q6_organisation_temps=5,
            q7_utilite_formation=5,
            q8_adequation_besoins=4,
            q9_satisfaction_globale=5,
            commentaire="Bon deroulement.",
            recommandations="Continuer le suivi terrain.",
            modified_by=self.user,
        )

        self.formateur_call = AppelFormateur.objects.create(
            reference_code="FORM-001",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            formation=self.formation.nom,
            telephone=self.formateur.telephone,
            cohorte="1",
            status="termine",
            audio_file=SimpleUploadedFile(
                "formateur.mp3",
                b"fake-audio-formateur",
                content_type="audio/mpeg",
            ),
            q1_prerequis_apprenants=4,
            q2_interaction_apprenants=5,
            q3_competences_acquises=4,
            q4_gestion_administrative="RAS",
            q5_gestion_financiere="Suivi correct.",
            q6_communication="Communication fluide.",
            commentaires="Session bien maitrisee.",
            recommandations="Maintenir le rythme.",
            locked_by=self.user,
        )
        self.formateur_call_repeat = AppelFormateur.objects.create(
            reference_code="FORM-002",
            prestataire=self.prestataire.raison_sociale,
            beneficiaire=self.beneficiaire.nom_structure,
            formation=self.formation.nom,
            telephone=self.formateur.telephone,
            cohorte="1",
            status="a_rappeler",
            locked_by=self.user,
        )

    def test_class_analysis_detail_is_accessible_by_lowercase_code(self):
        response = self.client.get(reverse("class_analysis_detail", args=["cla001"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CLA001")
        self.assertContains(response, "Apprenants (1)")
        self.assertContains(response, "Formateurs (2)")
        self.assertContains(response, "Chapeau de satisfaction")
        self.assertContains(response, "TOTAL DES PARTICIPANTS A LA FORMATION")
        self.assertContains(response, "Ecouter")
        self.assertContains(response, "Formulaire")
        self.assertContains(
            response,
            reverse("analysis_apprenant_call_detail", args=[self.apprenant_call.pk]),
        )
        self.assertContains(
            response,
            reverse("analysis_formateur_call_detail", args=[self.formateur_call.pk]),
        )

    def test_prefixed_root_redirects_authenticated_user_to_prefixed_dashboard(self):
        response = self.client.get("/padesce/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/padesce/dashboard/")

    def test_prefixed_class_analysis_detail_route_renders_prefixed_links(self):
        response = self.client.get("/padesce/classe/cla001/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CLA001")
        self.assertContains(response, 'href="/padesce/dashboard/"', html=False)
        self.assertContains(
            response,
            "/padesce/analyse/appels/apprenant/",
            html=False,
        )

    def test_prestation_analysis_detail_lists_linked_classes(self):
        response = self.client.get(reverse("prestation_analysis_detail", args=["presta146"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRESTA146")
        self.assertContains(response, "Classes de la prestation")
        self.assertContains(response, "CLA001")
        self.assertContains(response, "CLA002")
        self.assertContains(response, reverse("class_analysis_detail", args=[self.classe.code]))

    @patch("App_PADESCE.formations.views.build_padesce_source_index")
    def test_class_analysis_detail_ignores_cutoff_records_for_formateur_rows(
        self, mock_source_index
    ):
        mock_source_index.return_value = {
            "classes": {
                "cla001": {
                    "classe_id": "CLA001",
                    "teams_channel_url": "https://teams.microsoft.com/l/channel/fake",
                }
            },
            "records": {
                "call001": {
                    "code": "CALL001",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "formation": self.formation.nom,
                    "classe_id": self.classe.code,
                    "telephone1": "677001122",
                }
            },
        }

        response = self.client.get(reverse("class_analysis_detail", args=["cla001"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formateurs (2)")
        self.assertContains(response, "699001122")

    @patch("App_PADESCE.formations.views.build_padesce_source_index")
    def test_prestation_analysis_detail_ignores_cutoff_records_for_formateur_rows(
        self, mock_source_index
    ):
        mock_source_index.return_value = {
            "classes": {
                "cla001": {
                    "classe_id": "CLA001",
                    "teams_channel_url": "https://teams.microsoft.com/l/channel/fake",
                },
                "cla002": {
                    "classe_id": "CLA002",
                    "teams_channel_url": "https://teams.microsoft.com/l/channel/fake-2",
                },
            },
            "records": {
                "call001": {
                    "code": "CALL001",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "formation": self.formation.nom,
                    "classe_id": self.classe.code,
                    "telephone1": "677001122",
                }
            },
        }

        response = self.client.get(reverse("prestation_analysis_detail", args=["presta146"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Formateurs (2)")
        self.assertContains(response, "699001122")

    def test_read_only_call_detail_pages_render_without_start_actions(self):
        apprenant_response = self.client.get(
            reverse("analysis_apprenant_call_detail", args=[self.apprenant_call.pk])
        )
        formateur_response = self.client.get(
            reverse("analysis_formateur_call_detail", args=[self.formateur_call.pk])
        )

        self.assertEqual(apprenant_response.status_code, 200)
        self.assertEqual(formateur_response.status_code, 200)
        self.assertContains(apprenant_response, "Lecture seule - appel apprenant")
        self.assertContains(apprenant_response, "Questions renseignees")
        self.assertNotContains(apprenant_response, "Demarrer")
        self.assertContains(formateur_response, "Lecture seule - appel formateur")
        self.assertContains(formateur_response, "Questions notees")
        self.assertNotContains(formateur_response, "Demarrer")

    @patch("App_PADESCE.formations.views.build_padesce_source_index")
    def test_class_analysis_detail_falls_back_to_source_when_class_is_not_synced(
        self, mock_source_index
    ):
        self.apprenant_call.classe = None
        self.apprenant_call.classe_label = "CLA001"
        self.apprenant_call.save(update_fields=["classe", "classe_label"])
        self.classe.delete()

        mock_source_index.return_value = {
            "classes": {
                "cla001": {
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA146",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "cohorte": "1",
                    "lieu": self.lieu.nom_lieu,
                    "formation": self.formation.nom,
                    "statut_prestation": "Terminee",
                }
            },
            "prestations": {
                "presta146": {
                    "prestation_id": "PRESTA146",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "formation": self.formation.nom,
                    "fenetre": "2",
                }
            },
            "records": {},
        }

        response = self.client.get(reverse("class_analysis_detail", args=["cla001"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CLA001")
        self.assertContains(response, "PRESTA146")
        self.assertContains(response, "Fiche reconstituee depuis la source")
        self.assertContains(response, "Apprenants (1)")
        self.assertContains(response, "Formateurs (2)")

    @patch("App_PADESCE.formations.views.build_padesce_source_index")
    def test_prestation_analysis_detail_falls_back_to_source_when_missing_in_db(
        self, mock_source_index
    ):
        self.apprenant_call.classe = None
        self.apprenant_call.classe_label = "CLA001"
        self.apprenant_call.save(update_fields=["classe", "classe_label"])
        self.prestation.delete()

        mock_source_index.return_value = {
            "classes": {
                "cla001": {
                    "classe_id": "CLA001",
                    "prestation_id": "PRESTA146",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "cohorte": "1",
                    "lieu": self.lieu.nom_lieu,
                    "formation": self.formation.nom,
                    "statut_prestation": "Terminee",
                }
            },
            "prestations": {
                "presta146": {
                    "prestation_id": "PRESTA146",
                    "prestataire": self.prestataire.raison_sociale,
                    "beneficiaire": self.beneficiaire.nom_structure,
                    "formation": self.formation.nom,
                    "fenetre": "2",
                }
            },
            "records": {},
        }

        response = self.client.get(reverse("prestation_analysis_detail", args=["presta146"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PRESTA146")
        self.assertContains(response, "CLA001")
        self.assertContains(response, "Fiche reconstituee depuis la source")
