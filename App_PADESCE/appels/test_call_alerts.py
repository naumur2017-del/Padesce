import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.appels.models import CallAlert


class CallAlertApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.operator = User.objects.create_user(username="operateur", password="pass")
        self.admin = User.objects.create_user(
            username="superadmin",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_ACCEPT="application/json",
        )

    def test_operator_can_create_structured_call_alert(self):
        self.client.force_login(self.operator)

        response = self.post_json(
            reverse("call_alert_create"),
            {
                "source": "padesce",
                "alert_types": ["statut_ne_change_pas", "audio_non_enregistre"],
                "details": "Le statut reste en pause.",
                "page_path": "/appels/",
                "call_id": "42",
                "call_label": "Test appel",
                "call_status": "pause",
                "last_actions": [{"label": "Terminer", "row_id": "42"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        alert = CallAlert.objects.get()
        self.assertEqual(alert.reporter, self.operator)
        self.assertEqual(alert.source, "padesce")
        self.assertEqual(alert.status, CallAlert.STATUS_TODO)
        self.assertEqual(alert.alert_types, ["statut_ne_change_pas", "audio_non_enregistre"])
        self.assertEqual(alert.call_id, "42")

    def test_admin_done_requires_resolution_comment_and_sets_reaction_time(self):
        alert = CallAlert.objects.create(
            reporter=self.operator,
            source=CallAlert.SOURCE_CGA,
            alert_types=["appel_ne_demarre_pas"],
            details="Bouton demarrer inactif.",
        )
        self.client.force_login(self.admin)

        missing_comment = self.post_json(
            reverse("call_alert_update", args=[alert.pk]),
            {"status": "done", "admin_message": "Traite."},
        )
        self.assertEqual(missing_comment.status_code, 400)

        response = self.post_json(
            reverse("call_alert_update", args=[alert.pk]),
            {
                "status": "done",
                "admin_message": "Le correctif est applique.",
                "resolution_comment": "Cache local vide et appel relance.",
            },
        )

        self.assertEqual(response.status_code, 200)
        alert.refresh_from_db()
        self.assertEqual(alert.status, CallAlert.STATUS_DONE)
        self.assertEqual(alert.assigned_to, self.admin)
        self.assertIsNotNone(alert.first_response_at)
        self.assertIsNotNone(alert.resolved_at)
        self.assertEqual(alert.resolution_comment, "Cache local vide et appel relance.")
