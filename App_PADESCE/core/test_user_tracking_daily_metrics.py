from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from App_PADESCE.appels.models import Appel, AppelPasFormeII
from App_PADESCE.core.models import UserActivity
from App_PADESCE.core.views import _compute_tracking_payload


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class UserTrackingDailyMetricsTests(TestCase):
    def _set_appel_updated_at(self, appel, updated_at):
        Appel.objects.filter(pk=appel.pk).update(updated_at=updated_at)
        appel.refresh_from_db()
        return appel

    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_user(
            username="super-tracking",
            password="test-pass-123",
            is_superuser=True,
            is_staff=True,
        )
        self.agent = user_model.objects.create_user(
            username="agent-tracking",
            password="test-pass-123",
        )

        UserActivity.objects.create(
            user=self.agent,
            last_seen=timezone.now(),
            current_page="/appels/",
            current_page_title="Appels PADESCE",
        )

        self.yesterday_call = Appel.objects.create(
            code="TRK001",
            nom="Appel veille",
            locked_by=self.agent,
            status="appel_tente",
            is_active=True,
        )
        self.today_call = Appel.objects.create(
            code="TRK002",
            nom="Appel jour",
            locked_by=self.agent,
            status="appel_reussi",
            is_active=True,
        )

    def test_user_tracking_shows_calls_since_start_of_day(self):
        day_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        self._set_appel_updated_at(self.yesterday_call, day_start - timedelta(minutes=15))
        self._set_appel_updated_at(self.today_call, day_start + timedelta(hours=1))

        payload = _compute_tracking_payload(user_search="", call_scope="padesce")
        row = next(
            item
            for item in payload["user_activity_rows"]
            if item["username"] == "agent-tracking"
        )
        self.assertEqual(row["total_appels"], 2)
        self.assertEqual(row["appels_aujourdhui"], 1)

    def test_user_tracking_includes_pas_forme_ii_calls(self):
        AppelPasFormeII.objects.create(
            reference_code="PFII-TRACK-001",
            prestation_id="PRESTA-TRACK",
            nom="Appel Pas Forme II",
            locked_by=self.agent,
            status="formulaire_rempli",
            is_active=True,
        )

        payload = _compute_tracking_payload(user_search="", call_scope="padesce")
        row = next(item for item in payload["user_activity_rows"] if item["username"] == "agent-tracking")
        self.assertEqual(row["total_appels"], 3)
        self.assertEqual(row["formulaires_remplis"], 1)
        self.assertEqual(row["termines"], 1)

    def test_user_tracking_counts_today_forms_with_and_without_audio(self):
        Appel.objects.create(
            code="TRK003",
            nom="Formulaire sans audio",
            locked_by=self.agent,
            status="formulaire_rempli",
            is_active=True,
        )
        AppelPasFormeII.objects.create(
            reference_code="PFII-TRACK-AUDIO",
            prestation_id="PRESTA-TRACK",
            nom="Formulaire avec audio",
            locked_by=self.agent,
            status="formulaire_avec_audio",
            is_active=True,
        )

        payload = _compute_tracking_payload(user_search="", call_scope="padesce")
        row = next(item for item in payload["user_activity_rows"] if item["username"] == "agent-tracking")

        self.assertEqual(row["formulaires_sans_audio_aujourdhui"], 1)
        self.assertEqual(row["formulaires_avec_audio_aujourdhui"], 1)
        self.assertEqual(payload["formulaires_remplis_aujourdhui"], 2)

    def test_tracking_page_displays_today_form_counts(self):
        Appel.objects.create(
            code="TRK004",
            nom="Sans audio",
            locked_by=self.agent,
            status="formulaire_rempli",
            is_active=True,
        )
        AppelPasFormeII.objects.create(
            reference_code="PFII-TRACK-PAGE-AUDIO",
            prestation_id="PRESTA-TRACK",
            nom="Avec audio",
            locked_by=self.agent,
            status="formulaire_avec_audio",
            is_active=True,
        )
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("user_tracking"))

        self.assertContains(response, "Formulaires remplis aujourd’hui (depuis 00h)")
        self.assertContains(response, "Sans audio aujourd’hui")
        self.assertContains(response, "Avec audio aujourd’hui")
        self.assertEqual(response.context["formulaires_remplis_aujourdhui"], 2)
