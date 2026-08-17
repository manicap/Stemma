from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase


ELEVATED_PERMISSION_KEYS = {
    ("accounts", "view_restricted_content"),
    ("accounts", "view_admin_only_content"),
    ("people", "view_archived_person"),
    ("people", "view_deleted_person"),
}
PERSON_EDITOR_PERMISSION_KEY = ("people", "change_person")


class InitialPermissionGroupTests(TestCase):
    """Ověření systémových skupin a jejich minimálních oprávnění."""

    migration = import_module(
        "accounts.migrations.0003_initial_permission_groups"
    )

    def group_permission_keys(self, group: Group) -> set[tuple[str, str]]:
        return set(
            group.permissions.values_list(
                "content_type__app_label",
                "codename",
            )
        )

    def test_system_groups_exist(self) -> None:
        self.assertEqual(
            set(
                Group.objects.filter(
                    name__in=("Čtenář", "Editor", "Správce")
                ).values_list("name", flat=True)
            ),
            {"Čtenář", "Editor", "Správce"},
        )

    def test_all_custom_permissions_exist_with_exact_names(self) -> None:
        expected = {
            (
                "accounts",
                "view_restricted_content",
            ): "Může zobrazit omezený obsah",
            (
                "accounts",
                "view_admin_only_content",
            ): "Může zobrazit obsah pouze pro správce",
            (
                "people",
                "view_archived_person",
            ): "Může zobrazit archivované osoby",
            (
                "people",
                "view_deleted_person",
            ): "Může zobrazit měkce odstraněné osoby",
        }
        actual = {
            (permission.content_type.app_label, permission.codename): (
                permission.name
            )
            for permission in Permission.objects.select_related(
                "content_type"
            ).filter(
                content_type__app_label__in=("accounts", "people"),
                codename__in={key[1] for key in expected},
            )
        }

        self.assertEqual(actual, expected)

    def test_reader_and_editor_have_no_elevated_permissions(self) -> None:
        for group_name in ("Čtenář", "Editor"):
            with self.subTest(group=group_name):
                keys = self.group_permission_keys(
                    Group.objects.get(name=group_name)
                )
                self.assertTrue(keys.isdisjoint(ELEVATED_PERMISSION_KEYS))

    def test_person_edit_permission_matches_approved_roles(self) -> None:
        reader_keys = self.group_permission_keys(Group.objects.get(name="Čtenář"))
        editor_keys = self.group_permission_keys(Group.objects.get(name="Editor"))
        administrator_keys = self.group_permission_keys(
            Group.objects.get(name="Správce")
        )

        self.assertNotIn(PERSON_EDITOR_PERMISSION_KEY, reader_keys)
        self.assertIn(PERSON_EDITOR_PERMISSION_KEY, editor_keys)
        self.assertIn(PERSON_EDITOR_PERMISSION_KEY, administrator_keys)

    def test_administrator_has_all_four_elevated_permissions(self) -> None:
        keys = self.group_permission_keys(Group.objects.get(name="Správce"))

        self.assertTrue(ELEVATED_PERMISSION_KEYS.issubset(keys))
        self.assertNotIn(("accounts", "add_user"), keys)
        self.assertNotIn(("people", "delete_person"), keys)

    def test_group_membership_does_not_change_user_flags(self) -> None:
        user = get_user_model().objects.create_user(username="administrator")
        user.groups.add(Group.objects.get(name="Správce"))
        user.refresh_from_db()

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_forward_migration_is_idempotent_and_repairs_assignments(
        self,
    ) -> None:
        permissions = Permission.objects.filter(
            content_type__app_label__in=("accounts", "people"),
            codename__in={key[1] for key in ELEVATED_PERMISSION_KEYS},
        )
        reader = Group.objects.get(name="Čtenář")
        editor = Group.objects.get(name="Editor")
        administrator = Group.objects.get(name="Správce")
        reader.permissions.add(*permissions)
        editor.permissions.add(*permissions)
        administrator.permissions.remove(*permissions)
        Permission.objects.filter(
            content_type__app_label="accounts",
            codename="view_restricted_content",
        ).update(name="Dočasný název")

        self.migration.configure_permission_groups(apps, None)
        self.migration.configure_permission_groups(apps, None)

        self.assertTrue(
            self.group_permission_keys(reader).isdisjoint(
                ELEVATED_PERMISSION_KEYS
            )
        )
        self.assertTrue(
            self.group_permission_keys(editor).isdisjoint(
                ELEVATED_PERMISSION_KEYS
            )
        )
        self.assertTrue(
            ELEVATED_PERMISSION_KEYS.issubset(
                self.group_permission_keys(administrator)
            )
        )
        self.assertEqual(
            Permission.objects.get(
                content_type__app_label="accounts",
                codename="view_restricted_content",
            ).name,
            "Může zobrazit omezený obsah",
        )

    def test_reverse_only_removes_bindings_and_preserves_data(self) -> None:
        user = get_user_model().objects.create_user(username="member")
        administrator = Group.objects.get(name="Správce")
        user.groups.add(administrator)
        permission_ids = set(
            Permission.objects.filter(
                content_type__app_label__in=("accounts", "people"),
                codename__in={key[1] for key in ELEVATED_PERMISSION_KEYS},
            ).values_list("pk", flat=True)
        )

        self.migration.unconfigure_permission_groups(apps, None)

        self.assertEqual(
            Group.objects.filter(
                name__in=("Čtenář", "Editor", "Správce")
            ).count(),
            3,
        )
        self.assertEqual(
            Permission.objects.filter(pk__in=permission_ids).count(),
            4,
        )
        self.assertTrue(
            get_user_model().objects.get(pk=user.pk).groups.filter(
                name="Správce"
            ).exists()
        )
        for group in Group.objects.filter(
            name__in=("Čtenář", "Editor", "Správce")
        ):
            self.assertTrue(
                self.group_permission_keys(group).isdisjoint(
                    ELEVATED_PERMISSION_KEYS
                )
            )


class PersonEditorPermissionMigrationTests(TestCase):
    migration = import_module(
        "accounts.migrations.0004_person_editor_permissions"
    )

    def permission(self) -> Permission:
        return Permission.objects.get(
            content_type__app_label="people",
            codename="change_person",
        )

    def test_forward_is_idempotent_and_repairs_approved_roles(self) -> None:
        permission = self.permission()
        reader = Group.objects.get(name="Čtenář")
        editor = Group.objects.get(name="Editor")
        administrator = Group.objects.get(name="Správce")
        reader.permissions.add(permission)
        editor.permissions.remove(permission)
        administrator.permissions.remove(permission)

        self.migration.grant_person_editor_permission(apps, None)
        self.migration.grant_person_editor_permission(apps, None)

        self.assertFalse(reader.permissions.filter(pk=permission.pk).exists())
        self.assertTrue(editor.permissions.filter(pk=permission.pk).exists())
        self.assertTrue(
            administrator.permissions.filter(pk=permission.pk).exists()
        )

    def test_reverse_removes_only_role_bindings_and_preserves_permission(
        self,
    ) -> None:
        permission = self.permission()
        editor = Group.objects.get(name="Editor")
        user = get_user_model().objects.create_user(username="editor-member")
        user.groups.add(editor)

        self.migration.revoke_person_editor_permission(apps, None)

        self.assertTrue(Permission.objects.filter(pk=permission.pk).exists())
        self.assertTrue(Group.objects.filter(pk=editor.pk).exists())
        self.assertTrue(
            get_user_model().objects.get(pk=user.pk).groups.filter(
                pk=editor.pk
            ).exists()
        )
        self.assertFalse(
            Group.objects.filter(
                name__in=("Editor", "Správce"),
                permissions=permission,
            ).exists()
        )
