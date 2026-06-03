from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from App_PADESCE.core.models import UserActivity


class AdminPanelUserManagementTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin-panel-probe",
            email="admin-panel@example.com",
            password="StrongAdminPass123!",
        )
        self.client.force_login(self.admin_user)

    def test_admin_user_password_and_group_management_do_not_500(self):
        User = get_user_model()
        urls = [
            reverse("admin:index"),
            reverse("admin:auth_user_changelist"),
            reverse("admin:auth_user_add"),
            reverse("admin:auth_user_change", args=[self.admin_user.pk]),
            reverse("admin:auth_user_password_change", args=[self.admin_user.pk]),
            reverse("admin:auth_group_changelist"),
            reverse("admin:auth_group_add"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertLess(response.status_code, 500)

        response = self.client.post(
            reverse("admin:auth_user_add"),
            {
                "username": "admin-created-user",
                "usable_password": "true",
                "password1": "NewUserStrongPass123!",
                "password2": "NewUserStrongPass123!",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(username="admin-created-user")
        self.assertTrue(created.check_password("NewUserStrongPass123!"))
        self.assertIsNone(created.last_login)

        response = self.client.post(
            reverse("admin:auth_user_password_change", args=[created.pk]),
            {
                "password1": "ChangedStrongPass123!",
                "password2": "ChangedStrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertTrue(created.check_password("ChangedStrongPass123!"))

        response = self.client.post(
            reverse("admin:auth_group_add"),
            {"name": "module-admin-test", "permissions": [], "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Group.objects.filter(name="module-admin-test").exists())

        self.assertFalse(UserActivity.objects.filter(user=self.admin_user).exists())
