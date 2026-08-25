from django.conf import settings
from django.test import SimpleTestCase


class PublicAnalysisAutoLoginDefaultTests(SimpleTestCase):
    def test_auto_login_is_disabled_by_default(self):
        self.assertFalse(settings.PUBLIC_ANALYSIS_AUTO_LOGIN)
        self.assertEqual(settings.PUBLIC_ANALYSIS_AUTO_LOGIN_USERNAME, "")
        self.assertEqual(settings.PUBLIC_ANALYSIS_AUTO_LOGIN_PASSWORD, "")
