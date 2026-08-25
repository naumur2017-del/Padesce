from django.test import RequestFactory, SimpleTestCase, override_settings

from App_PADESCE.core.auth_throttling import OperatorLoginAttemptLimiter


@override_settings(
    PADESCE_AUTH_THROTTLE_ENABLED=True,
    PADESCE_AUTH_THROTTLE_ALLOW_LOCAL_CACHE_FOR_TESTS=True,
    PADESCE_AUTH_THROTTLE_MAX_FAILURES=2,
    PADESCE_AUTH_THROTTLE_WINDOW_SECONDS=60,
)
class OperatorLoginAttemptLimiterTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().post("/login/", REMOTE_ADDR="203.0.113.8")
        self.limiter = OperatorLoginAttemptLimiter()

    def tearDown(self):
        self.limiter.reset(self.request, "operatrice-a")
        self.limiter.reset(self.request, "operatrice-b")

    def test_blocks_only_the_same_identifier_and_ip_pair(self):
        self.assertFalse(self.limiter.is_blocked(self.request, "operatrice-a"))
        self.limiter.record_failure(self.request, "operatrice-a")
        self.limiter.record_failure(self.request, "operatrice-a")

        self.assertTrue(self.limiter.is_blocked(self.request, "operatrice-a"))
        self.assertFalse(self.limiter.is_blocked(self.request, "operatrice-b"))

    def test_success_resets_only_its_own_attempt_counter(self):
        self.limiter.record_failure(self.request, "operatrice-a")
        self.limiter.record_failure(self.request, "operatrice-a")
        self.assertTrue(self.limiter.is_blocked(self.request, "operatrice-a"))

        self.limiter.reset(self.request, "operatrice-a")

        self.assertFalse(self.limiter.is_blocked(self.request, "operatrice-a"))
