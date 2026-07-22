from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from . import permissions
from .choices import AccessLevel
from .permissions import can_view_access_level


class AccessLevelPermissionApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu permission helperu."""

    def test_public_api_and_keyword_only_parameters_are_exact(self) -> None:
        self.assertEqual(permissions.__all__, ("can_view_access_level",))
        parameters = signature(can_view_access_level).parameters
        self.assertEqual(tuple(parameters), ("actor", "access_level"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class AccessLevelPermissionTests(TestCase):
    """Ověření obecné AccessLevel policy nad aktuálním stavem actora."""

    def create_user(self, username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    def get_permission(self, codename: str) -> Permission:
        return Permission.objects.get(
            content_type__app_label="accounts",
            content_type__model="user",
            codename=codename,
        )

    def assert_error_code(
        self,
        *,
        actor,
        access_level: str,
        key: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            can_view_access_level(
                actor=actor,
                access_level=access_level,
            )

        self.assertEqual(context.exception.error_dict[key][0].code, code)

    def test_public_is_visible_to_every_actor_kind(self) -> None:
        actors = (
            AnonymousUser(),
            self.create_user("active"),
            self.create_user("inactive", is_active=False),
            self.create_user("staff", is_staff=True),
            self.create_user("superuser", is_superuser=True),
        )

        for actor in actors:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.assertTrue(
                    can_view_access_level(
                        actor=actor,
                        access_level=AccessLevel.PUBLIC,
                    )
                )

    def test_authenticated_requires_active_existing_user(self) -> None:
        active = self.create_user("active-authenticated")
        inactive = self.create_user(
            "inactive-authenticated",
            is_active=False,
        )

        self.assertFalse(
            can_view_access_level(
                actor=AnonymousUser(),
                access_level=AccessLevel.AUTHENTICATED,
            )
        )
        self.assertTrue(
            can_view_access_level(
                actor=active,
                access_level=AccessLevel.AUTHENTICATED,
            )
        )
        self.assertFalse(
            can_view_access_level(
                actor=inactive,
                access_level=AccessLevel.AUTHENTICATED,
            )
        )

    def test_unsaved_and_physically_missing_authenticated_actor(self) -> None:
        unsaved = get_user_model()(username="unsaved")
        missing = self.create_user("missing")
        get_user_model().objects.filter(pk=missing.pk).delete()

        for actor in (unsaved, missing):
            with self.subTest(actor=actor.username):
                self.assert_error_code(
                    actor=actor,
                    access_level=AccessLevel.AUTHENTICATED,
                    key="actor",
                    code="actor_unsaved",
                )

    def test_restricted_visibility_variants(self) -> None:
        permission = self.get_permission("view_restricted_content")
        ordinary = self.create_user("restricted-ordinary")
        direct = self.create_user("restricted-direct")
        direct.user_permissions.add(permission)
        via_group = self.create_user("restricted-group")
        group = Group.objects.create(name="Restricted test")
        group.permissions.add(permission)
        via_group.groups.add(group)
        staff = self.create_user("restricted-staff", is_staff=True)
        superuser = self.create_user(
            "restricted-superuser",
            is_superuser=True,
        )
        inactive = self.create_user(
            "restricted-inactive",
            is_active=False,
        )
        inactive.user_permissions.add(permission)
        inactive_superuser = self.create_user(
            "restricted-inactive-superuser",
            is_active=False,
            is_superuser=True,
        )

        expectations = (
            (AnonymousUser(), False),
            (ordinary, False),
            (direct, True),
            (via_group, True),
            (staff, False),
            (superuser, True),
            (inactive, False),
            (inactive_superuser, False),
        )
        for actor, expected in expectations:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.assertIs(
                    can_view_access_level(
                        actor=actor,
                        access_level=AccessLevel.RESTRICTED,
                    ),
                    expected,
                )

    def test_admin_only_visibility_variants(self) -> None:
        permission = self.get_permission("view_admin_only_content")
        ordinary = self.create_user("admin-ordinary")
        direct = self.create_user("admin-direct")
        direct.user_permissions.add(permission)
        via_group = self.create_user("admin-group")
        group = Group.objects.create(name="Admin content test")
        group.permissions.add(permission)
        via_group.groups.add(group)
        staff = self.create_user("admin-staff", is_staff=True)
        superuser = self.create_user("admin-superuser", is_superuser=True)
        inactive = self.create_user("admin-inactive", is_active=False)
        inactive.user_permissions.add(permission)
        inactive_superuser = self.create_user(
            "admin-inactive-superuser",
            is_active=False,
            is_superuser=True,
        )

        expectations = (
            (AnonymousUser(), False),
            (ordinary, False),
            (direct, True),
            (via_group, True),
            (staff, False),
            (superuser, True),
            (inactive, False),
            (inactive_superuser, False),
        )
        for actor, expected in expectations:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.assertIs(
                    can_view_access_level(
                        actor=actor,
                        access_level=AccessLevel.ADMIN_ONLY,
                    ),
                    expected,
                )

    def test_invalid_actor_and_access_level_use_stable_errors(self) -> None:
        for actor in (None, object()):
            with self.subTest(actor=actor):
                self.assert_error_code(
                    actor=actor,
                    access_level=AccessLevel.PUBLIC,
                    key="actor",
                    code="actor_invalid",
                )

        self.assert_error_code(
            actor=AnonymousUser(),
            access_level="unknown",
            key="access_level",
            code="invalid_access_level",
        )

    def test_uses_current_is_active_database_value(self) -> None:
        actor = self.create_user("stale-active")
        get_user_model().objects.filter(pk=actor.pk).update(is_active=False)

        self.assertFalse(
            can_view_access_level(
                actor=actor,
                access_level=AccessLevel.AUTHENTICATED,
            )
        )

    def test_uses_permission_added_after_actor_was_loaded(self) -> None:
        actor = self.create_user("permission-added")
        permission = self.get_permission("view_restricted_content")
        get_user_model().objects.get(pk=actor.pk).user_permissions.add(
            permission
        )

        self.assertTrue(
            can_view_access_level(
                actor=actor,
                access_level=AccessLevel.RESTRICTED,
            )
        )

    def test_does_not_use_permission_removed_after_actor_was_loaded(self) -> None:
        permission = self.get_permission("view_restricted_content")
        actor = self.create_user("permission-removed")
        actor.user_permissions.add(permission)
        stale_actor = get_user_model().objects.get(pk=actor.pk)
        actor.user_permissions.remove(permission)

        self.assertFalse(
            can_view_access_level(
                actor=stale_actor,
                access_level=AccessLevel.RESTRICTED,
            )
        )
