from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase, override_settings

from App_PADESCE.core.operator_auth_backends import OperatorAuthenticationBackend
from App_PADESCE.core.auth_views import SQLiteSafeLoginView
from App_PADESCE.core.operator_login_forms import OperatorLoginForm


@override_settings(PADESCE_OPERATOR_LOGIN_REQUIRED_GROUPS=("operatrice",))
class OperatorAuthenticationBackendTests(TestCase):
    def setUp(self):
        self.backend = OperatorAuthenticationBackend()
        self.operator_group = Group.objects.create(name="operatrice")

    def test_authenticates_a_normalized_identifier_for_an_authorized_operator(self):
        user = get_user_model().objects.create_user(
            username="Opératrice", password="safe-test-password"
        )
        user.groups.add(self.operator_group)

        authenticated = self.backend.authenticate(
            request=None,
            username="\u00a0OPÉRATRICE\u200b",
            password="safe-test-password",
        )

        self.assertEqual(authenticated, user)

    def test_success_log_has_a_technical_code_and_no_raw_identifier(self):
        user = get_user_model().objects.create_user(
            username="Opératrice", password="safe-test-password"
        )
        user.groups.add(self.operator_group)

        with self.assertLogs("App_PADESCE.auth", level="INFO") as logs:
            authenticated = self.backend.authenticate(
                request=None, username="Opératrice", password="safe-test-password"
            )

        self.assertEqual(authenticated, user)
        message = "\n".join(logs.output)
        self.assertIn("code=AUTH_SUCCESS", message)
        self.assertIn("correlation_id=", message)
        self.assertIn("duration_ms=", message)
        self.assertNotIn("Opératrice", message)

    def test_rejects_a_normalized_identifier_collision(self):
        first = get_user_model().objects.create_user(
            username="Operatrice", password="safe-test-password"
        )
        second = get_user_model().objects.create_user(
            username=" operatrice ", password="another-test-password"
        )
        first.groups.add(self.operator_group)
        second.groups.add(self.operator_group)

        authenticated = self.backend.authenticate(
            request=None, username="operatrice", password="safe-test-password"
        )

        self.assertIsNone(authenticated)

    def test_rejects_an_account_without_an_authorized_group(self):
        get_user_model().objects.create_user(username="operatrice", password="safe-test-password")

        authenticated = self.backend.authenticate(
            request=None, username="operatrice", password="safe-test-password"
        )

        self.assertIsNone(authenticated)

    @override_settings(PADESCE_OPERATOR_LOGIN_REQUIRED_GROUPS=())
    def test_fails_closed_when_no_authorized_group_is_configured(self):
        user = get_user_model().objects.create_user(
            username="operatrice", password="safe-test-password"
        )
        user.groups.add(self.operator_group)

        authenticated = self.backend.authenticate(
            request=None, username="operatrice", password="safe-test-password"
        )

        self.assertIsNone(authenticated)


@override_settings(
    AUTHENTICATION_BACKENDS=("App_PADESCE.core.operator_auth_backends.OperatorAuthenticationBackend",),
    PADESCE_OPERATOR_AUTH_ENABLED=True,
    PADESCE_OPERATOR_LOGIN_REQUIRED_GROUPS=("operatrice",),
)
class OperatorLoginFormTests(TestCase):
    def setUp(self):
        operator_group = Group.objects.create(name="operatrice")
        self.user = get_user_model().objects.create_user(
            username="Opératrice", password="safe-test-password"
        )
        self.user.groups.add(operator_group)

    def test_form_authenticates_with_the_shared_normalization(self):
        form = OperatorLoginForm(
            request=RequestFactory().post("/login/"),
            data={"username": "\u00a0OPÉRATRICE\u200b", "password": "safe-test-password"},
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_login_view_uses_the_operator_form_only_when_feature_is_enabled(self):
        view = SQLiteSafeLoginView()

        self.assertIs(view.get_form_class(), OperatorLoginForm)

    @override_settings(
        PADESCE_AUTH_THROTTLE_ENABLED=True,
        PADESCE_AUTH_THROTTLE_ALLOW_LOCAL_CACHE_FOR_TESTS=True,
        PADESCE_AUTH_THROTTLE_MAX_FAILURES=1,
    )
    def test_form_temporarily_blocks_only_after_a_failed_attempt(self):
        request = RequestFactory().post("/login/", REMOTE_ADDR="203.0.113.8")
        invalid_form = OperatorLoginForm(
            request=request,
            data={"username": "Opératrice", "password": "wrong-password"},
        )
        self.assertFalse(invalid_form.is_valid())

        blocked_form = OperatorLoginForm(
            request=request,
            data={"username": "Opératrice", "password": "safe-test-password"},
        )

        self.assertFalse(blocked_form.is_valid())
        self.assertIn("Identifiant ou mot de passe incorrect.", blocked_form.non_field_errors())
