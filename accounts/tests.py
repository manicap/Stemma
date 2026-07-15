"""Tests for the Stemma user model."""

from django.contrib.auth import get_user_model
from django.test import TestCase


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