from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class ProtectedDebugViewsTests(TestCase):
    def setUp(self):
        self.client.raise_request_exception = False
        self.regular_user = get_user_model().objects.create_user(
            username="debug-regular",
            password="test-pass-123",
        )
        self.staff_user = get_user_model().objects.create_user(
            username="debug-staff",
            password="test-pass-123",
            is_staff=True,
        )

    @override_settings(DEBUG=False)
    def test_debug_endpoints_return_404_for_non_staff_users_in_production(self):
        self.client.force_login(self.regular_user)

        for path in ("/debug-formateur-stats/", "/test-stats-minimal/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    @patch(
        "App_PADESCE.core.public_views._build_formateur_stats_simple",
        return_value={"best_rankings": [], "improve_rankings": [], "summary_cards": []},
    )
    def test_staff_users_can_access_protected_debug_endpoints(self, _mock_stats):
        self.client.force_login(self.staff_user)

        response = self.client.get("/debug-formateur-stats/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/test-stats-minimal/")
        self.assertEqual(response.status_code, 200)
