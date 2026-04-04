from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import override_settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import Appel, AppelAnswers, padesce_form_tracking_cutoff
from App_PADESCE.core.analysis_rules import (
    appel_analysis_exclusion_reason,
    appel_is_analysis_eligible,
)
from App_PADESCE.core.views import _consultant_analysis_snapshot
from App_PADESCE.core.models import UserActivity


class DashboardVisibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="standard-user",
            password="test-pass-123",
        )
        self.manager = user_model.objects.create_user(
            username="manager-user",
            password="test-pass-123",
        )
        self.consultant = user_model.objects.create_user(
            username="consultant-user",
            password="test-pass-123",
        )
        self.superuser = user_model.objects.create_user(
            username="nav-superuser",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        consultant_group, _ = Group.objects.get_or_create(name="consultant")
        self.manager.groups.add(manager_group)
        self.consultant.groups.add(consultant_group)

    def test_regular_user_does_not_see_analysis_links(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_view_call_cards"])
        self.assertFalse(response.context["can_view_analysis_pages"])
        self.assertContains(response, "Ouvrir PADESCE")
        self.assertContains(response, "Ouvrir CGA")
        self.assertContains(response, "Ouvrir appels formateurs")
        self.assertContains(response, "Analyses Satisfaction", count=0)
        self.assertContains(response, "PADESCE - KPIs Dernieres 24h", count=0)

    def test_manager_sees_analysis_links(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_view_analysis_pages"])
        self.assertContains(response, "Analyses Satisfaction")

    def test_regular_user_nav_shows_only_call_links(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Appels Padesce")
        self.assertContains(response, "Appel Formateur")
        self.assertContains(response, "CGA")
        self.assertNotContains(response, "Analyse Enquete Apprenants")
        self.assertNotContains(response, "Backup")
        self.assertNotContains(response, "Admin")

    def test_consultant_only_nav_hides_restricted_links(self):
        self.client.force_login(self.consultant)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Analyse Enquete Apprenants")
        self.assertNotContains(response, "Appels Padesce")
        self.assertNotContains(response, "Appel Formateur")
        self.assertNotContains(response, "Analyse Enquete Formateur")
        self.assertNotContains(response, 'href="/reporting/"', html=False)
        self.assertNotContains(response, 'href="/cga/"', html=False)
        self.assertNotContains(response, "Backup")

    def test_superuser_nav_shows_superadmin_links(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Backup")
        self.assertContains(response, "Deploiement Gandi")
        self.assertContains(response, "Admin")


class AnalysisEligibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.yanava, _ = user_model.objects.get_or_create(username="yanava")
        self.yanava.set_password("test-pass-123")
        self.yanava.is_active = True
        self.yanava.save(update_fields=["password", "is_active"])

    def test_yanava_answer_with_phone_is_now_eligible(self):
        appel = Appel.objects.create(
            code="APP-YAN-001",
            nom="Apprenant Joignable",
            telephone1="690001111",
            fenetre="2",
            is_active=True,
        )
        answer = AppelAnswers.objects.create(
            appel=appel,
            q1_clarte_exposes=4,
            q2_interaction_formateur=4,
            q3_maitrise_contenu=4,
            q4_salle_adequate=4,
            q5_materiel_disponible=4,
            q6_organisation_temps=4,
            q7_utilite_formation=4,
            q8_adequation_besoins=4,
            q9_satisfaction_globale=4,
            modified_by=self.yanava,
        )

        self.assertEqual(appel_analysis_exclusion_reason(appel, answer=answer), "")
        self.assertTrue(appel_is_analysis_eligible(appel, answer=answer))

    def test_yanava_answer_without_phone_stays_excluded_for_missing_phone(self):
        appel = Appel.objects.create(
            code="APP-YAN-002",
            nom="Apprenant Sans Numero",
            fenetre="2",
            is_active=True,
        )
        answer = AppelAnswers.objects.create(
            appel=appel,
            q1_clarte_exposes=4,
            q2_interaction_formateur=4,
            q3_maitrise_contenu=4,
            q4_salle_adequate=4,
            q5_materiel_disponible=4,
            q6_organisation_temps=4,
            q7_utilite_formation=4,
            q8_adequation_besoins=4,
            q9_satisfaction_globale=4,
            modified_by=self.yanava,
        )

        self.assertEqual(appel_analysis_exclusion_reason(appel, answer=answer), "Sans numero")
        self.assertFalse(appel_is_analysis_eligible(appel, answer=answer))


class SuperadminTrackingTests(TestCase):
    def _create_answers(self, appel, modified_by, *, created_at, modified_at):
        answers = AppelAnswers.objects.create(
            appel=appel,
            q1_clarte_exposes=5,
            q2_interaction_formateur=5,
            q3_maitrise_contenu=5,
            q4_salle_adequate=5,
            q5_materiel_disponible=5,
            q6_organisation_temps=5,
            q7_utilite_formation=5,
            q8_adequation_besoins=5,
            q9_satisfaction_globale=5,
            commentaire="RAS",
            recommandations="RAS",
            modified_by=modified_by,
            modified_at=modified_at,
        )
        AppelAnswers.objects.filter(pk=answers.pk).update(
            created_at=created_at,
            updated_at=modified_at,
            modified_at=modified_at,
        )
        return AppelAnswers.objects.get(pk=answers.pk)

    def _set_appel_updated_at(self, appel, updated_at):
        Appel.objects.filter(pk=appel.pk).update(updated_at=updated_at)
        appel.refresh_from_db()
        return appel

    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_user(
            username="super-dashboard",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )
        self.agent = user_model.objects.create_user(
            username="agent-dashboard",
            password="test-pass-123",
        )
        self.other_agent = user_model.objects.create_user(
            username="other-agent",
            password="test-pass-123",
        )
        self.form_cutoff = padesce_form_tracking_cutoff()
        UserActivity.objects.create(user=self.agent, last_seen=timezone.now())
        UserActivity.objects.create(user=self.other_agent, last_seen=timezone.now())

        current_call = Appel.objects.create(
            code="APP900",
            nom="Apprenant En Cours",
            locked_by=self.agent,
            status="en_cours",
            is_active=True,
        )
        legacy_termine = Appel.objects.create(
            code="APP901",
            nom="Apprenant Termine Ancien",
            locked_by=self.agent,
            status="termine",
            is_active=True,
        )
        Appel.objects.create(
            code="APP902",
            nom="Apprenant Rappel",
            locked_by=self.agent,
            status="a_rappeler",
            is_active=True,
        )
        audio_termine = Appel.objects.create(
            code="APP903",
            nom="Apprenant Audio",
            locked_by=self.agent,
            status="termine",
            is_active=True,
            audio_file="padesce/tests/audio.mp3",
        )
        modified_elsewhere = Appel.objects.create(
            code="APP904",
            nom="Apprenant Modifie",
            locked_by=self.other_agent,
            status="pause",
            is_active=True,
        )

        self._set_appel_updated_at(legacy_termine, self.form_cutoff - timedelta(days=2))
        self._set_appel_updated_at(audio_termine, self.form_cutoff + timedelta(days=2))
        self._set_appel_updated_at(current_call, self.form_cutoff + timedelta(days=1))
        self._set_appel_updated_at(modified_elsewhere, self.form_cutoff + timedelta(days=3))

        self._create_answers(
            current_call,
            self.agent,
            created_at=self.form_cutoff + timedelta(days=1),
            modified_at=self.form_cutoff + timedelta(days=1),
        )
        self._create_answers(
            modified_elsewhere,
            self.agent,
            created_at=self.form_cutoff + timedelta(days=1),
            modified_at=self.form_cutoff + timedelta(days=2),
        )

    def test_superadmin_dashboard_shows_user_tracking_table(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suivi des utilisateurs PADESCE")
        self.assertContains(response, 'name="user_search"', html=False)
        self.assertContains(response, "agent-dashboard")
        self.assertContains(response, "?agent=agent-dashboard")
        self.assertContains(response, "?agent=agent-dashboard&amp;status=en_cours")
        self.assertContains(response, '?agent=agent-dashboard&amp;formulaire=rempli">1</a>', html=False)
        self.assertContains(
            response,
            '?modified_by=agent-dashboard&amp;formulaire=modifie">1</a>',
            html=False,
        )
        self.assertContains(
            response,
            '?tracking_termine=1&amp;tracking_user=agent-dashboard">4</a>',
            html=False,
        )
        self.assertContains(response, "APP900 - Apprenant En Cours")

    def test_superadmin_dashboard_sorts_rows_by_finished_calls(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        rows = response.context["user_activity_rows"]
        self.assertEqual(rows[0]["username"], "agent-dashboard")
        agent_row = next(row for row in rows if row["username"] == "agent-dashboard")
        self.assertEqual(agent_row["formulaires_remplis"], 1)
        self.assertEqual(agent_row["formulaires_modifies"], 1)
        self.assertEqual(agent_row["termines"], 4)
        self.assertEqual(agent_row["a_rappeler"], 1)
        self.assertEqual(agent_row["en_cours"], 1)

    def test_superadmin_dashboard_filters_users_by_search(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("home"), {"user_search": "other"})

        self.assertEqual(response.status_code, 200)
        rows = response.context["user_activity_rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "other-agent")


@override_settings(
    DEBUG=True,
    ROOT_URLCONF="App_PADESCE.core.test_error_urls",
    ALLOWED_HOSTS=["testserver"],
)
class FriendlyErrorPagesTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="error-page-user",
            password="test-pass-123",
        )
        self.client.force_login(self.user)
        self.client.raise_request_exception = False

    def test_custom_404_page_is_used_in_debug(self):
        response = self.client.get("/missing/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "La page demandee est introuvable ou a ete deplacee.", status_code=404)
        self.assertContains(response, "contactez l'equipe de maintenance", html=False, status_code=404)
        self.assertNotContains(response, "The current path", status_code=404)

    def test_custom_500_page_is_used_in_debug(self):
        response = self.client.get("/server-error/")

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Une interruption technique a empeche l", status_code=500)
        self.assertContains(response, "Aucune information technique sensible n'est affichee sur cette page.", status_code=500)
        self.assertNotContains(response, "Traceback", status_code=500)

    def test_custom_400_page_is_used_in_debug(self):
        response = self.client.get("/bad-request/")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "La demande n", status_code=400)
        self.assertContains(response, "contactez l'equipe de maintenance", html=False, status_code=400)

    def test_custom_403_page_is_used_in_debug(self):
        response = self.client.get("/forbidden/")

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Cette page n", status_code=403)
        self.assertContains(response, "Equipe de maintenance", status_code=403)

    def test_json_error_responses_are_preserved(self):
        response = self.client.get("/json-forbidden/", HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "keep-json"})


class PublicConsultantAccessTests(TestCase):
    @override_settings(PUBLIC_CONSULTANT_ACCESS=True)
    @patch("App_PADESCE.core.views._consultant_analysis_snapshot")
    def test_consultant_dashboard_is_public_when_enabled(self, mock_snapshot):
        mock_snapshot.return_value = {
            "class_options": [{"value": "CLA001", "label": "CLA001 - Formation test"}],
            "prestataire_options": ["Prestataire test"],
            "beneficiaire_options": ["Beneficiaire test"],
            "fenetre_options": ["2", "3"],
            "counts": {
                "analyzed_classes_count": 1,
                "analyzed_prestations_count": 1,
                "analyzed_prestataires_count": 1,
                "analyzed_beneficiaires_count": 1,
                "analysis_audio_count": 3,
                "analyzed_learners_count": 10,
                "total_apprenants": 10,
            },
        }

        response = self.client.get(reverse("consultant_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prestations")
        self.assertContains(response, "Classes")
        self.assertContains(response, "Apprenants analyses")
        self.assertContains(response, "Nombre d'audios")

    @override_settings(PUBLIC_CONSULTANT_ACCESS=False)
    def test_consultant_dashboard_redirects_when_public_access_disabled(self):
        response = self.client.get(reverse("consultant_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response["Location"])

    @override_settings(PUBLIC_CONSULTANT_ACCESS=True)
    def test_login_page_shows_consultant_direct_button(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Espace PADESCE")
        self.assertContains(response, reverse("consultant_dashboard"))

    @override_settings(PUBLIC_CONSULTANT_ACCESS=True)
    @patch("App_PADESCE.core.views._consultant_analysis_snapshot")
    @patch("App_PADESCE.core.views._consultant_audio_duration_seconds")
    def test_consultant_dashboard_prioritizes_long_audios_with_completed_forms(
        self,
        mock_audio_duration,
        mock_snapshot,
    ):
        mock_snapshot.return_value = {
            "class_options": [],
            "prestataire_options": [],
            "beneficiaire_options": [],
            "fenetre_options": [],
            "counts": {
                "analyzed_classes_count": 0,
                "analyzed_prestations_count": 0,
                "analyzed_prestataires_count": 0,
                "analyzed_beneficiaires_count": 0,
                "total_apprenants": 0,
            },
        }

        prioritized = Appel.objects.create(
            code="APP950",
            nom="Alpha Prioritaire",
            classe_label="CLA001",
            fenetre="2",
            telephone1="690000950",
            status="termine",
            is_active=True,
            audio_file="padesce/tests/prioritaire.mp3",
        )
        audio_only = Appel.objects.create(
            code="APP951",
            nom="Beta Audio",
            classe_label="CLA001",
            fenetre="2",
            telephone1="690000951",
            status="termine",
            is_active=True,
            audio_file="padesce/tests/audio-seul.mp3",
        )
        form_only = Appel.objects.create(
            code="APP952",
            nom="Gamma Formulaire",
            classe_label="CLA001",
            fenetre="2",
            telephone1="690000952",
            status="termine",
            is_active=True,
        )

        AppelAnswers.objects.create(
            appel=prioritized,
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
        AppelAnswers.objects.create(
            appel=form_only,
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

        mock_audio_duration.side_effect = lambda appel: {prioritized.pk: 75.0}.get(appel.pk)

        response = self.client.get(reverse("consultant_dashboard"))

        self.assertEqual(response.status_code, 200)
        rows = list(response.context["rows"])
        self.assertEqual(rows[0].pk, prioritized.pk)
        self.assertFalse(getattr(rows[1], "consultant_priority", False))
        self.assertContains(response, "Nombre d'audios")

    @override_settings(PUBLIC_CONSULTANT_ACCESS=True)
    def test_consultant_detail_simulates_missing_answers_for_display(self):
        appel = Appel.objects.create(
            code="APP960",
            nom="Apprenant Sans Numero",
            classe_label="CLA001",
            status="termine",
            is_active=True,
        )

        response = self.client.get(reverse("consultant_call_detail", args=[appel.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "9/9")
        self.assertContains(response, "Les notes manquantes ont ete completees automatiquement")
        self.assertContains(response, "numero joignable dans le dossier")
        self.assertNotContains(response, "<td>-</td>", html=False)


class PublicAnalysisAutoLoginTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.auto_user, _ = user_model.objects.get_or_create(username="yanava")
        self.auto_user.set_password("PADESCE1234")
        self.auto_user.is_active = True
        self.auto_user.save(update_fields=["password", "is_active"])
        manager_group, _ = Group.objects.get_or_create(name="manager_padesce")
        self.auto_user.groups.add(manager_group)

    @override_settings(
        PUBLIC_ANALYSIS_AUTO_LOGIN=True,
        PUBLIC_ANALYSIS_AUTO_LOGIN_USERNAME="yanava",
        PUBLIC_ANALYSIS_AUTO_LOGIN_PASSWORD="PADESCE1234",
    )
    def test_fast_stats_api_auto_logs_anonymous_user(self):
        response = self.client.get(reverse("fast_stats_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.auto_user.pk)
        self.assertIn("generated_at", response.json())

    @override_settings(
        PUBLIC_ANALYSIS_AUTO_LOGIN=True,
        PUBLIC_ANALYSIS_AUTO_LOGIN_USERNAME="yanava",
        PUBLIC_ANALYSIS_AUTO_LOGIN_PASSWORD="wrong-password",
    )
    def test_fast_stats_api_redirects_when_auto_login_credentials_are_invalid(self):
        response = self.client.get(reverse("fast_stats_api"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(
        PUBLIC_ANALYSIS_AUTO_LOGIN=True,
        PUBLIC_ANALYSIS_AUTO_LOGIN_USERNAME="yanava",
        PUBLIC_ANALYSIS_AUTO_LOGIN_PASSWORD="PADESCE1234",
    )
    def test_regular_dashboard_stays_protected(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)


class BackupTriggerAccessTests(TestCase):
    @override_settings(BACKUP_TRIGGER_TOKEN="expected-token")
    @patch("App_PADESCE.core.backup_manager.start_backup", return_value="job-123")
    def test_backup_trigger_is_not_redirected_to_login(self, mock_start_backup):
        response = self.client.post(
            reverse("backup_trigger"),
            content_type="application/json",
            HTTP_X_BACKUP_TOKEN="expected-token",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["job_id"], "job-123")
        mock_start_backup.assert_called_once_with(triggered_by="scheduled/github-actions")

    @override_settings(BACKUP_TRIGGER_TOKEN="expected-token")
    def test_backup_trigger_returns_403_for_invalid_token(self):
        response = self.client.post(reverse("backup_trigger"), HTTP_X_BACKUP_TOKEN="wrong-token")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Token invalide ou manquant."})


class ConsultantAnalysisSnapshotTests(SimpleTestCase):
    @patch("App_PADESCE.satisfaction_apprenants.views._build_satisfaction_dashboard_data")
    def test_consultant_snapshot_reuses_satisfaction_dashboard_counts(self, mock_build_dashboard_data):
        mock_build_dashboard_data.return_value = {
            "context": {
                "total": 200,
                "analyzed_classes_count": 174,
                "analyzed_prestations_count": 49,
                "analyzed_prestataires_count": 12,
                "analyzed_beneficiaires_count": 10,
                "classe_stats": [
                    {"code": "CLA012", "intitule": "Gestion d'entreprise"},
                    {"code": "CLA014", "intitule": "Elevage"},
                ],
                "analyzed_prestataires": [
                    {"label": "Prestataire Alpha", "nb": 70},
                    {"label": "Prestataire Beta", "nb": 12},
                ],
                "analyzed_beneficiaires": [
                    {"label": "Beneficiaire A", "nb": 50},
                    {"label": "Beneficiaire B", "nb": 30},
                ],
                "analyzed_fenetres": [
                    {"label": "2", "nb": 100},
                    {"label": "3", "nb": 100},
                ],
            }
        }

        snapshot = _consultant_analysis_snapshot(
            SimpleNamespace(is_authenticated=True),
            classe_filter="CLA012",
            prestataire_filter="Prestataire Alpha",
        )

        self.assertEqual(snapshot["counts"]["analyzed_classes_count"], 174)
        self.assertEqual(snapshot["counts"]["analyzed_prestations_count"], 49)
        self.assertEqual(snapshot["counts"]["analyzed_prestataires_count"], 12)
        self.assertEqual(snapshot["counts"]["analyzed_beneficiaires_count"], 10)
        self.assertEqual(snapshot["counts"]["total_apprenants"], 200)
        self.assertEqual(
            snapshot["class_options"],
            [
                {"value": "CLA012", "label": "CLA012 - Gestion d'entreprise"},
                {"value": "CLA014", "label": "CLA014 - Elevage"},
            ],
        )
        self.assertEqual(snapshot["prestataire_options"], ["Prestataire Alpha", "Prestataire Beta"])
        self.assertEqual(snapshot["beneficiaire_options"], ["Beneficiaire A", "Beneficiaire B"])
        self.assertEqual(snapshot["fenetre_options"], ["2", "3"])

        fake_request = mock_build_dashboard_data.call_args[0][0]
        self.assertEqual(fake_request.GET.get("classe"), "CLA012")
        self.assertEqual(fake_request.GET.get("prestataire"), "Prestataire Alpha")
