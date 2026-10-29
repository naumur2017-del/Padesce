from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from App_PADESCE.appels.cga_views import _build_filtered_cga_queryset
from App_PADESCE.appels.models import AppelCGA
from App_PADESCE.core.access import (
    has_analysis_access,
    has_consultant_access,
    user_group_names,
)
from App_PADESCE.core.middleware import LoginRequiredMiddleware, UserActivityMiddleware


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "navigation-performance-tests",
        }
    },
    PADESCE_ENABLE_ACTIVITY_TRACKING=True,
)
class NavigationPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="navigation-agent")
        self.consultant, _ = Group.objects.get_or_create(name="consultant")
        self.manager, _ = Group.objects.get_or_create(name="manager_cga")
        self.factory = RequestFactory()

    def test_access_checks_share_one_role_query(self):
        self.user.groups.add(self.consultant)

        with self.assertNumQueries(1):
            self.assertTrue(has_consultant_access(self.user))
            self.assertTrue(has_analysis_access(self.user))
            self.assertIn("consultant", user_group_names(self.user))

    def test_role_cache_is_reloaded_on_the_next_request(self):
        self.user.groups.add(self.consultant)
        self.assertNotIn("manager_cga", user_group_names(self.user))
        self.user.groups.add(self.manager)
        request = self.factory.get("/cga/")
        request.user = self.user

        response = LoginRequiredMiddleware(lambda request: HttpResponse("OK"))(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn("manager_cga", user_group_names(self.user))

    def test_repeated_navigation_does_not_read_activity_again(self):
        request = self.factory.get("/cga/")
        request.user = self.user
        middleware = UserActivityMiddleware(lambda request: HttpResponse("OK"))
        with patch("App_PADESCE.core.middleware.UserActivity.objects.filter") as query:
            query.return_value.first.return_value = SimpleNamespace(last_seen=timezone.now())
            self.assertEqual(middleware(request).status_code, 200)
            self.assertEqual(middleware(request).status_code, 200)
            self.assertEqual(query.call_count, 1)

    def test_cga_filter_options_select_unique_values_in_the_database(self):
        AppelCGA.objects.bulk_create(
            [
                AppelCGA(
                    niu=f"PERF-{index}",
                    raison_sociale=f"Entreprise {index}",
                    regime="Simplifie",
                    cri="Centre",
                    centre_de_rattachement="CGA A",
                    ville="Douala",
                    source=AppelCGA.SOURCE_ENTREPRISE,
                )
                for index in range(20)
            ]
        )
        request = self.factory.get("/cga/")
        with CaptureQueriesContext(connection) as queries:
            _, filters = _build_filtered_cga_queryset(request)

        self.assertEqual(filters["villes"], ["Douala"])
        self.assertEqual(filters["regimes"], ["Simplifie"])
        self.assertEqual(len(queries), 5)
        self.assertTrue(all("SELECT DISTINCT" in item["sql"] for item in queries))

        with self.assertNumQueries(0):
            rows, cached_filters = _build_filtered_cga_queryset(request)
        self.assertEqual(cached_filters["villes"], ["Douala"])
        # A cached label set must never cache call state or its queryset results.
        AppelCGA.objects.filter(niu="PERF-0").update(status="en_cours")
        self.assertEqual(rows.get(niu="PERF-0").status, "en_cours")

    def test_legacy_cga_transcription_reports_unavailable_without_crashing(self):
        self.client.force_login(self.user)
        response = self.client.get("/cga/tools/transcribe-filtered-status/")
        self.assertEqual(response.status_code, 501)
        self.assertFalse(response.json()["ok"])
        self.assertIn("pas configurée", response.json()["error"])
