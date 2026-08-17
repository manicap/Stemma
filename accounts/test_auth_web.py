from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from common.choices import AccessLevel
from people.models import Person


class AuthenticationWebTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="reader",
            password="test-password",
        )

    def test_anonymous_topbar_links_to_login_with_local_return_path(self) -> None:
        response = self.client.get(reverse("people:index"))

        self.assertContains(response, "Přihlásit se")
        self.assertContains(response, "next=/osoby/")
        self.assertNotContains(response, "Odhlásit se")

    def test_login_authenticates_and_returns_to_safe_local_next(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "reader",
                "password": "test-password",
                "next": reverse("people:index"),
            },
        )

        self.assertRedirects(response, reverse("people:index"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_rejects_external_next_url(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "reader",
                "password": "test-password",
                "next": "https://attacker.example/steal",
            },
        )

        self.assertRedirects(response, reverse("common:overview"))

    def test_invalid_login_has_usable_error_without_authentication(self) -> None:
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "reader", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zadejte správnou hodnotu")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_log_in(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=("is_active",))

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "reader", "password": "test-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_topbar_shows_identity_and_post_logout(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("people:index"))

        self.assertContains(response, "reader")
        self.assertContains(response, "Odhlásit se")
        self.assertNotContains(response, ">Přihlásit se</a>")

    def test_logout_is_post_only_and_clears_session(self) -> None:
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("accounts:logout"))
        post_response = self.client.post(reverse("accounts:logout"))

        self.assertEqual(get_response.status_code, 405)
        self.assertRedirects(post_response, reverse("common:overview"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf_token(self) -> None:
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 403)


class RoleWebFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.public_person = Person.objects.create(
            first_name="Veřejná",
            access_level=AccessLevel.PUBLIC,
        )
        cls.authenticated_person = Person.objects.create(
            first_name="Přihlášená",
            access_level=AccessLevel.AUTHENTICATED,
        )
        cls.restricted_person = Person.objects.create(
            first_name="Omezená",
            access_level=AccessLevel.RESTRICTED,
        )

    def create_role_user(self, username: str, group_name: str):
        user = get_user_model().objects.create_user(
            username=username,
            password="test-password",
        )
        user.groups.add(Group.objects.get(name=group_name))
        return user

    def test_reader_sees_authenticated_content_without_edit_permission(self) -> None:
        reader = self.create_role_user("role-reader", "Čtenář")
        self.client.force_login(reader)

        response = self.client.get(reverse("people:index"))

        self.assertContains(response, "Veřejná")
        self.assertContains(response, "Přihlášená")
        self.assertNotContains(response, "Omezená")
        self.assertFalse(reader.has_perm("people.change_person"))

    def test_editor_sees_authenticated_content_and_has_edit_permission(self) -> None:
        editor = self.create_role_user("role-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.get(reverse("people:index"))

        self.assertContains(response, "Veřejná")
        self.assertContains(response, "Přihlášená")
        self.assertNotContains(response, "Omezená")
        self.assertTrue(editor.has_perm("people.change_person"))

    def test_administrator_gets_edit_and_elevated_content_permissions(self) -> None:
        administrator = self.create_role_user("role-admin", "Správce")
        self.client.force_login(administrator)

        response = self.client.get(reverse("people:index"))

        self.assertContains(response, "Omezená")
        self.assertTrue(administrator.has_perm("people.change_person"))
