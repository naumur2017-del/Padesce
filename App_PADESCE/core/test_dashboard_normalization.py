from django.test import SimpleTestCase

from App_PADESCE.core.views import _sorted_distinct_non_empty_strings


class DashboardOptionNormalizationTests(SimpleTestCase):
    def test_sorted_distinct_non_empty_strings_ignores_blank_and_null_like_values(self):
        values = ["  Beta  ", "", None, "Alpha", "   ", "Beta", 3, "3"]

        result = _sorted_distinct_non_empty_strings(values)

        self.assertEqual(result, ["3", "Alpha", "Beta"])
