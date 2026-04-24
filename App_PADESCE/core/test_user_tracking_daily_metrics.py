from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from App_PADESCE.appels.models import Appel
from App_PADESCE.core.models import UserActivity
from App_PADESCE.core.views import _compute_tracking_payload


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
