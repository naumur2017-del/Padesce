import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.appels.models import AppelCGA


class CGAArgumentaireTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="conseiller",
            first_name="Aline",
            password="test-password",
        )
        self.client.force_login(self.user)
        self.appel = AppelCGA.objects.create(
            source=AppelCGA.SOURCE_SUIVI,
            campaign_month=datetime.date(2026, 8, 1),
            raison_sociale="Atelier Exemple",
            niu="SUIVI-001",
            activite_principale="Menuiserie",
            telephone="699000001",
        )

    def test_suivi_page_contains_personalized_call_script_and_immediate_opening(self):
        response = self.client.get(reverse("cga_index"), {"source": "suivi"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="js-call-script-modal"')
        self.assertContains(response, 'data-name="Atelier Exemple"')
        self.assertContains(response, 'data-activity="Menuiserie"')
        self.assertContains(response, "votre conseiller au CGA NAUMUR")
        self.assertContains(response, "openCallScript(row);")
        self.assertContains(response, "Argumentaire</span>")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(response["X-PADESCE-CGA-UI-Version"], "argumentaire-v2")

    def test_other_cga_sources_do_not_show_follow_up_script(self):
        response = self.client.get(reverse("cga_index"), {"source": "entreprise"})

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="js-call-script-modal"')

    def test_call_outcome_is_saved_when_a_reminder_is_scheduled(self):
        response = self.client.post(
            reverse("cga_action", args=[self.appel.pk]),
            {
                "action": "rappeler",
                "rappel_at": "2026-08-24T10:30",
                "interet": "OUI",
                "mauvais_numero": "NON",
                "indisponible": "NON",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.appel.refresh_from_db()
        self.assertEqual(self.appel.status, "a_rappeler")
        self.assertEqual(self.appel.interet, "OUI")
        self.assertIsNotNone(self.appel.rappel_at)
