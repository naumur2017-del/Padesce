from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.contrib.auth.models import Group
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import Appel, AppelAnswers
from App_PADESCE.core.analysis_rules import (
    appel_analysis_exclusion_reason,
    appel_is_analysis_eligible,
)
from App_PADESCE.core.models import UserActivity, UserActivityEvent
from App_PADESCE.core.views import _consultant_analysis_snapshot


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


class UserActivityMiddlewareFallbackTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="middleware-fallback-user",
            password="test-pass-123",
        )

    @patch(
        "App_PADESCE.core.middleware.UserActivity.objects.filter",
        side_effect=OperationalError("missing column"),
    )
    def test_missing_useractivity_column_does_not_break_request(self, _mock_filter):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)


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

    def test_not_formed_flag_excludes_reachable_learner_from_analysis(self):
        appel = Appel.objects.create(
            code="APP-NF-001",
            nom="Apprenant Non Forme",
            telephone1="690001999",
            fenetre="2",
            is_active=True,
            flag_pas_forme=True,
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

        self.assertEqual(
            appel_analysis_exclusion_reason(appel, answer=answer), "Pas suivi formation"
        )
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
        UserActivity.objects.create(
            user=self.agent,
            last_seen=timezone.now(),
            last_ip="196.216.2.10",
            last_latitude=4.0511,
            last_longitude=9.7679,
            last_city="Douala",
            last_country="Cameroon",
            current_page="/appels/",
            current_page_title="Appels Padesce",
            last_action_type="button_click",
            last_action_label="Sauvegarder",
            last_action_target="save-call",
            last_action_at=timezone.now(),
        )
        UserActivity.objects.create(
            user=self.other_agent,
            last_seen=timezone.now(),
            last_ip="41.202.10.12",
            last_latitude=3.848,
            last_longitude=11.5021,
            last_city="Yaounde",
            last_country="Cameroon",
            current_page="/dashboard/",
            current_page_title="Dashboard",
            last_action_type="page_view",
            last_action_label="Dashboard",
            last_action_target="/dashboard/",
            last_action_at=timezone.now(),
        )
        UserActivityEvent.objects.create(
            user=self.agent,
            event_type=UserActivityEvent.EVENT_PAGE_VIEW,
            page_path="/appels/",
            page_title="Appels Padesce",
            target_label="Appels Padesce",
            target_path="/appels/",
        )
        UserActivityEvent.objects.create(
            user=self.agent,
            event_type=UserActivityEvent.EVENT_BUTTON_CLICK,
            page_path="/appels/",
            page_title="Appels Padesce",
            target_label="Sauvegarder",
            target_path="save-call",
        )

        Appel.objects.create(
            code="APP900",
            nom="Apprenant En Cours",
            locked_by=self.agent,
            status="appel_tente",
            is_active=True,
        )
        Appel.objects.create(
            code="APP901",
            nom="Apprenant Reussi",
            locked_by=self.agent,
            status="appel_reussi",
            is_active=True,
        )
        Appel.objects.create(
            code="APP902",
            nom="Apprenant Rappel",
            locked_by=self.agent,
            status="a_rappeler",
            is_active=True,
        )
        Appel.objects.create(
            code="APP903",
            nom="Apprenant Audio",
            locked_by=self.agent,
            status="formulaire_avec_audio",
            is_active=True,
            audio_file="padesce/tests/audio.mp3",
        )
        Appel.objects.create(
            code="APP904",
            nom="Apprenant Formulaire",
            locked_by=self.agent,
            status="formulaire_rempli",
            is_active=True,
        )
        Appel.objects.create(
            code="APP905",
            nom="Apprenant Autre Agent",
            locked_by=self.other_agent,
            status="appel_tente",
            is_active=True,
        )

    def test_superadmin_user_tracking_page_shows_user_tracking_table(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Suivi des utilisateurs PADESCE")
        self.assertContains(response, 'name="user_search"', html=False)
        self.assertContains(response, "agent-dashboard")
        self.assertContains(response, "?agent=agent-dashboard")
        self.assertContains(response, "?agent=agent-dashboard&amp;status=a_rappeler")
        self.assertContains(response, "?agent=agent-dashboard&amp;formulaire=rempli")
        self.assertContains(response, "?modified_by=agent-dashboard&amp;formulaire=modifie")
        self.assertContains(response, "APP900 - Apprenant En Cours")
        self.assertContains(response, "Adresse IP")
        self.assertContains(response, "Localisation")
        self.assertContains(response, "Carte du globe")
        self.assertContains(response, "Sauvegarder")
        self.assertContains(response, "Appels Padesce")
        self.assertContains(response, "Voir historique")

    def test_home_links_to_user_tracking_page(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("user_tracking"))
        self.assertNotContains(response, "Suivi des utilisateurs PADESCE")

    def test_superadmin_user_tracking_sorts_rows_by_finished_calls(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking"))

        self.assertEqual(response.status_code, 200)
        rows = response.context["user_activity_rows"]
        self.assertEqual(rows[0]["username"], "agent-dashboard")
        agent_row = next(row for row in rows if row["username"] == "agent-dashboard")
        self.assertEqual(agent_row["total_appels"], 5)
        self.assertEqual(agent_row["last_city"], "Douala")
        self.assertEqual(agent_row["last_country"], "Cameroon")
        self.assertEqual(agent_row["appels_tentes"], 1)
        self.assertEqual(agent_row["appels_reussis"], 1)
        self.assertEqual(agent_row["formulaires_remplis"], 1)
        self.assertEqual(agent_row["formulaires_avec_audio"], 1)
        self.assertEqual(agent_row["a_rappeler"], 1)
        self.assertEqual(agent_row["push_sur_main"], 0)
        self.assertEqual(agent_row["deploiements"], 0)

    def test_superadmin_user_tracking_filters_users_by_search(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking"), {"user_search": "other"})

        self.assertEqual(response.status_code, 200)
        rows = response.context["user_activity_rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "other-agent")

    @patch(
        "App_PADESCE.core.views.UserLoginLog.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    @patch(
        "App_PADESCE.core.views.UserActivityEvent.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    @patch(
        "App_PADESCE.core.views.UserActivity.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    def test_superadmin_user_tracking_page_handles_outdated_schema(self, *_mocks):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Certaines donnees de suivi avance sont temporairement indisponibles"
        )

    @patch(
        "App_PADESCE.core.views.UserLoginLog.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    @patch(
        "App_PADESCE.core.views.UserActivityEvent.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    @patch(
        "App_PADESCE.core.views.UserActivity.objects.select_related",
        side_effect=OperationalError("missing column"),
    )
    def test_superadmin_user_tracking_live_api_handles_outdated_schema(self, *_mocks):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking_live_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["tracking_schema_ready"])
        self.assertIn("super-dashboard", [row["username"] for row in payload["online_rows"]])


class ActivityTrackingApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="tracker-user",
            password="test-pass-123",
        )
        self.superuser = user_model.objects.create_user(
            username="tracker-admin",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )

    def test_activity_track_api_updates_user_activity_and_creates_event(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("activity_track_api"),
            data='{"event_type":"button_click","page_path":"/appels/","page_title":"Appels","target_label":"Valider","target_path":"#save"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        activity = UserActivity.objects.get(user=self.user)
        self.assertEqual(activity.current_page, "/appels/")
        self.assertEqual(activity.current_page_title, "Appels")
        self.assertEqual(activity.last_action_type, "button_click")
        self.assertEqual(activity.last_action_label, "Valider")
        self.assertTrue(
            UserActivityEvent.objects.filter(user=self.user, target_label="Valider").exists()
        )

    @patch(
        "App_PADESCE.core.views.UserActivity.objects.get_or_create",
        side_effect=OperationalError("missing column"),
    )
    def test_activity_track_api_ignores_outdated_schema(self, _mock_get_or_create):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("activity_track_api"),
            data='{"event_type":"button_click","page_path":"/appels/","page_title":"Appels","target_label":"Valider","target_path":"#save"}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "tracking_disabled": True})

    def test_superuser_live_api_returns_online_rows(self):
        UserActivity.objects.create(
            user=self.user,
            last_seen=timezone.now(),
            last_latitude=4.05,
            last_longitude=9.76,
            last_city="Douala",
            last_country="Cameroon",
            current_page="/appels/",
            current_page_title="Appels",
            last_action_type="button_click",
            last_action_label="Valider",
            last_action_target="#save",
            last_action_at=timezone.now(),
        )
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking_live_api"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["online_count"], 1)
        self.assertIn("tracker-user", [row["username"] for row in payload["online_rows"]])
        self.assertIn("Douala", [point["city"] for point in payload["globe_points"]])


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
        self.assertContains(
            response, "La page demandee est introuvable ou a ete deplacee.", status_code=404
        )
        self.assertContains(
            response, "contactez l'equipe de maintenance", html=False, status_code=404
        )
        self.assertNotContains(response, "The current path", status_code=404)

    def test_custom_500_page_is_used_in_debug(self):
        response = self.client.get("/server-error/")

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Une interruption technique a empeche l", status_code=500)
        self.assertContains(
            response,
            "Aucune information technique sensible n'est affichee sur cette page.",
            status_code=500,
        )
        self.assertNotContains(response, "Traceback", status_code=500)

    def test_custom_400_page_is_used_in_debug(self):
        response = self.client.get("/bad-request/")

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "La demande n", status_code=400)
        self.assertContains(
            response, "contactez l'equipe de maintenance", html=False, status_code=400
        )

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

    @override_settings(PUBLIC_CONSULTANT_ACCESS=True)
    def test_consultant_detail_allows_dashboard_rows_that_are_not_completed(self):
        appel = Appel.objects.create(
            code="APP961",
            nom="Apprenant Tente",
            classe_label="CLA001",
            fenetre="2",
            telephone1="690009961",
            status="appel_tente",
            is_active=True,
        )

        response = self.client.get(reverse("consultant_call_detail", args=[appel.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dossier PADESCE")
        self.assertContains(response, "Apprenant Tente")


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
    def test_consultant_snapshot_reuses_satisfaction_dashboard_counts(
        self, mock_build_dashboard_data
    ):
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


class AnalysisMaterializationTests(TestCase):
    @patch("App_PADESCE.appels.views._safe_build_padesce_source_index", return_value=None)
    @patch("App_PADESCE.appels.views._build_appel_class_progress_snapshot")
    def test_appel_optimization_reuses_db_when_fingerprint_unchanged(self, mock_build, _src):
        from App_PADESCE.core.analysis_materialization import get_or_build_appel_optimization_snapshot

        mock_build.return_value = {
            "source_bundle": None,
            "source_summary": {},
            "classe_progress": [],
            "classe_progress_all": [],
            "progress_by_key": {},
            "hidden_class_labels": [],
            "hidden_class_count": 0,
            "hidden_appel_count": 0,
            "classes_without_callable_phone_count": 0,
            "recommended_classes": [],
            "analysis_prestations_count": 0,
        }
        get_or_build_appel_optimization_snapshot()
        get_or_build_appel_optimization_snapshot()
        self.assertEqual(mock_build.call_count, 1)

    def test_materialized_dashboard_roundtrip(self):
        from App_PADESCE.core.analysis_materialization import (
            load_materialized_dashboard_payload,
            save_materialized_dashboard_payload,
        )

        key = "test-key-materialized"
        payload = {"rows": [], "filters": {"a": 1}, "context": {"n": 2}}
        save_materialized_dashboard_payload(key, payload, 3600)
        loaded = load_materialized_dashboard_payload(key)
        self.assertEqual(loaded, payload)

    def test_appels_list_metrics_cache_key_ignores_page(self):
        from App_PADESCE.core.analysis_materialization import appels_list_metrics_cache_key

        rf = RequestFactory()
        r1 = rf.get("/appels/", {"page": "1", "status": "termine"})
        r2 = rf.get("/appels/", {"page": "2", "status": "termine"})
        fp = "0::0"
        common = dict(
            appels_data_fingerprint=fp,
            source_workbook_fingerprint="none",
            hidden_class_labels=["A", "B"],
        )
        self.assertEqual(
            appels_list_metrics_cache_key(r1, **common),
            appels_list_metrics_cache_key(r2, **common),
        )


class FormateursDashboardMaterializationTests(TestCase):
    @patch("App_PADESCE.satisfaction_formateurs.views.build_fast_stats_context", return_value={})
    @patch("App_PADESCE.satisfaction_formateurs.views.render")
    @patch("App_PADESCE.satisfaction_formateurs.views._build_formateurs_dashboard_context")
    def test_dashboard_reuses_cache_between_requests(self, mock_build, mock_render, _fs):
        from django.contrib.auth.models import Group
        from django.core.cache import cache

        from App_PADESCE.satisfaction_formateurs.views import satisfaction_formateurs_dashboard

        cache.clear()
        mock_render.return_value = None
        mock_build.return_value = {
            "total": 0,
            "termines": 0,
            "with_scores": 0,
            "global_avgs": {},
            "q_labels": [],
            "prestataire_stats": [],
            "beneficiaire_stats": [],
            "cohorte_stats": [],
            "status_counts": {},
            "prestataires": [],
            "beneficiaires": [],
            "cohortes": [],
            "f_prestataire": "",
            "f_beneficiaire": "",
            "f_cohorte": "",
            "rows": [],
        }
        user_model = get_user_model()
        user = user_model.objects.create_user(username="dash-form-f", password="pw-test-12")
        mgr, _ = Group.objects.get_or_create(name="manager_padesce")
        user.groups.add(mgr)
        rf = RequestFactory()
        request = rf.get("/satisfaction-formateurs/dashboard/")
        request.user = user
        satisfaction_formateurs_dashboard(request)
        satisfaction_formateurs_dashboard(request)
        self.assertEqual(mock_build.call_count, 1)
