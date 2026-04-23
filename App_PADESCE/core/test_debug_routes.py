import importlib
from contextlib import contextmanager

from django.test import SimpleTestCase, override_settings
from django.urls import NoReverseMatch, clear_url_caches, reverse

import App_PADESCE.urls as project_urls


@contextmanager
def reloaded_project_urls(**overrides):
    with override_settings(**overrides):
        clear_url_caches()
        importlib.reload(project_urls)
        try:
            yield
        finally:
            clear_url_caches()

    importlib.reload(project_urls)
    clear_url_caches()


class DebugRouteRegistrationTests(SimpleTestCase):
    def test_debug_routes_are_hidden_when_debug_is_false(self):
        with reloaded_project_urls(DEBUG=False):
            with self.assertRaises(NoReverseMatch):
                reverse("test_stats_minimal")
            with self.assertRaises(NoReverseMatch):
                reverse("debug_formateur_stats")
            with self.assertRaises(NoReverseMatch):
                reverse("padesce:test_stats_minimal")
            with self.assertRaises(NoReverseMatch):
                reverse("padesce:debug_formateur_stats")

    def test_debug_routes_are_available_when_debug_is_true(self):
        with reloaded_project_urls(DEBUG=True):
            self.assertEqual(reverse("test_stats_minimal"), "/test-stats-minimal/")
            self.assertEqual(reverse("debug_formateur_stats"), "/debug-formateur-stats/")
