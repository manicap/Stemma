from io import StringIO
from secrets import token_urlsafe
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings


@override_settings(DEBUG=True)
class BootstrapDemoAccountsCommandTests(TestCase):
    def setUp(self) -> None:
        self.password = f"{token_urlsafe(24)}!Aa7"

    def run_command(self, password: str | None = None) -> str:
        chosen_password = password or self.password
        output = StringIO()
        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass",
            side_effect=(chosen_password, chosen_password),
        ):
            call_command("bootstrap_demo_accounts", stdout=output)
        return output.getvalue()

    def test_command_creates_login_ready_accounts_with_exact_roles(self) -> None:
        output = self.run_command()

        expected = {
            "stemma-demo-reader": "Čtenář",
            "stemma-demo-editor": "Editor",
            "stemma-demo-administrator": "Správce",
        }
        expected_permissions = {
            "stemma-demo-reader": set(),
            "stemma-demo-editor": {"people.change_person"},
            "stemma-demo-administrator": {
                "people.change_person",
                "accounts.view_restricted_content",
                "accounts.view_admin_only_content",
                "people.view_archived_person",
                "people.view_deleted_person",
            },
        }
        checked_permissions = {
            permission
            for permissions in expected_permissions.values()
            for permission in permissions
        }
        self.assertEqual(get_user_model().objects.count(), 3)
        for username, group_name in expected.items():
            with self.subTest(username=username):
                user = get_user_model().objects.get(username=username)
                self.assertEqual(
                    list(user.groups.values_list("name", flat=True)),
                    [group_name],
                )
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)
                self.assertTrue(user.is_active)
                self.assertIsNotNone(
                    authenticate(username=username, password=self.password)
                )
                self.assertEqual(
                    {
                        permission
                        for permission in checked_permissions
                        if user.has_perm(permission)
                    },
                    expected_permissions[username],
                )
                self.assertIn(username, output)
        self.assertNotIn(self.password, output)

    def test_repeated_run_is_idempotent_and_repairs_demo_identity(self) -> None:
        self.run_command()
        user = get_user_model().objects.get(username="stemma-demo-reader")
        administrator = Group.objects.get(name="Správce")
        editor_permission = Permission.objects.get(
            content_type__app_label="people",
            codename="change_person",
        )
        user.groups.set((administrator,))
        user.user_permissions.add(editor_permission)
        Group.objects.get(name="Čtenář").permissions.add(editor_permission)
        Group.objects.get(name="Editor").permissions.remove(editor_permission)
        administrator.permissions.remove(editor_permission)
        user.is_staff = True
        user.is_superuser = True
        user.is_active = False
        user.save()

        output = self.run_command()

        self.assertEqual(get_user_model().objects.count(), 3)
        user.refresh_from_db()
        self.assertEqual(
            list(user.groups.values_list("name", flat=True)),
            ["Čtenář"],
        )
        self.assertFalse(user.user_permissions.exists())
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertFalse(
            Group.objects.get(name="Čtenář").permissions.filter(
                pk=editor_permission.pk
            ).exists()
        )
        self.assertTrue(
            Group.objects.get(name="Editor").permissions.filter(
                pk=editor_permission.pk
            ).exists()
        )
        self.assertTrue(
            administrator.permissions.filter(pk=editor_permission.pk).exists()
        )
        self.assertIn("nové účty 0, resetované účty 3", output)

    def test_repeated_run_resets_all_passwords(self) -> None:
        self.run_command()
        replacement = f"{token_urlsafe(24)}!Aa7"

        self.run_command(replacement)

        for username in (
            "stemma-demo-reader",
            "stemma-demo-editor",
            "stemma-demo-administrator",
        ):
            with self.subTest(username=username):
                self.assertIsNone(
                    authenticate(username=username, password=self.password)
                )
                self.assertIsNotNone(
                    authenticate(username=username, password=replacement)
                )

    @override_settings(DEBUG=False)
    def test_command_fails_closed_without_prompt_outside_debug(self) -> None:
        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass"
        ) as prompt:
            with self.assertRaisesMessage(
                CommandError,
                "pouze v lokálním režimu DEBUG",
            ):
                call_command("bootstrap_demo_accounts")

        prompt.assert_not_called()
        self.assertFalse(get_user_model().objects.exists())

    def test_password_mismatch_does_not_create_accounts(self) -> None:
        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass",
            side_effect=(self.password, f"{token_urlsafe(24)}!Aa7"),
        ):
            with self.assertRaisesMessage(CommandError, "se neshodují"):
                call_command("bootstrap_demo_accounts")

        self.assertFalse(get_user_model().objects.exists())

    def test_invalid_password_does_not_create_accounts(self) -> None:
        with self.assertRaises(CommandError):
            self.run_command("short")

        self.assertFalse(get_user_model().objects.exists())

    def test_reserved_username_collision_fails_without_changes(self) -> None:
        collision = get_user_model().objects.create_user(
            username="stemma-demo-editor",
            email="owner@example.com",
            password=f"{token_urlsafe(24)}!Aa7",
        )

        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass"
        ) as prompt:
            with self.assertRaisesMessage(
                CommandError,
                "nevytvořil lokální demo bootstrap",
            ):
                call_command("bootstrap_demo_accounts")

        prompt.assert_not_called()
        self.assertEqual(get_user_model().objects.count(), 1)
        collision.refresh_from_db()
        self.assertEqual(collision.email, "owner@example.com")

    def test_missing_role_group_fails_before_prompt_or_write(self) -> None:
        Group.objects.get(name="Editor").delete()

        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass"
        ) as prompt:
            with self.assertRaisesMessage(CommandError, "spusťte migrace"):
                call_command("bootstrap_demo_accounts")

        prompt.assert_not_called()
        self.assertFalse(get_user_model().objects.exists())

    def test_missing_role_permission_fails_before_prompt_or_write(self) -> None:
        Permission.objects.get(
            content_type__app_label="people",
            codename="change_person",
        ).delete()

        with patch(
            "accounts.management.commands.bootstrap_demo_accounts.getpass"
        ) as prompt:
            with self.assertRaisesMessage(CommandError, "spusťte migrace"):
                call_command("bootstrap_demo_accounts")

        prompt.assert_not_called()
        self.assertFalse(get_user_model().objects.exists())

    def test_batch_rolls_back_when_later_account_save_fails(self) -> None:
        user_model = get_user_model()
        original_save = user_model.save
        save_count = 0

        def fail_second_save(instance, *args, **kwargs):
            nonlocal save_count
            save_count += 1
            if save_count == 2:
                raise RuntimeError("Simulované selhání dávky.")
            return original_save(instance, *args, **kwargs)

        with patch.object(user_model, "save", new=fail_second_save):
            with self.assertRaisesMessage(RuntimeError, "selhání dávky"):
                self.run_command()

        self.assertFalse(user_model.objects.exists())
