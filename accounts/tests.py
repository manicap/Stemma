"""Tests for the Stemma user model."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.test import TestCase

from materials.models import Vault

from .admin import StemmaUserAdmin


class UserModelTests(TestCase):
    """Verify the custom user model configuration."""

    def test_project_uses_accounts_user_model(self) -> None:
        user_model = get_user_model()

        self.assertEqual(user_model._meta.label, "accounts.User")

    def test_user_can_be_created_with_hashed_password(self) -> None:
        user_model = get_user_model()

        user = user_model.objects.create_user(
            username="testuser",
            password="strong-test-password",
        )

        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.check_password("strong-test-password"))
        self.assertNotEqual(user.password, "strong-test-password")
        self.assertEqual(user.vault.owner, user)

    def test_superuser_creation_provisions_owned_vault(self) -> None:
        user = get_user_model().objects.create_superuser(
            username="test-superuser",
            password="strong-test-password",
        )

        self.assertEqual(user.vault.owner, user)

    def test_admin_creation_provisions_owned_vault(self) -> None:
        user = get_user_model()(username="admin-created")
        model_admin = StemmaUserAdmin(get_user_model(), admin.site)

        model_admin.save_model(
            RequestFactory().post("/admin/accounts/user/add/"),
            user,
            form=None,
            change=False,
        )

        self.assertTrue(Vault.objects.filter(owner=user).exists())
