from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from people.models import Person

from . import selectors
from .choices import GraveSiteStatus
from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
    Place,
)
from .selectors import (
    get_grave_site_person_links,
    get_person_grave_site_links,
    get_visible_grave_site_person_links,
    get_visible_person_grave_site_links,
)


class VisiblePersonGraveSiteSelectorApiTests(SimpleTestCase):
    """Ověření veřejného API autorizovaných selectorů vazeb."""

    def test_module_exports_exact_approved_api(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "get_grave_site_person_links",
                "get_grave_sites",
                "get_person_grave_site_links",
                "get_person_residences",
                "get_visible_grave_site_person_links",
                "get_visible_grave_sites",
                "get_visible_person_grave_site_links",
                "get_visible_person_residences",
            ),
        )
        self.assertIs(
            selectors.get_visible_person_grave_site_links,
            get_visible_person_grave_site_links,
        )
        self.assertIs(
            selectors.get_visible_grave_site_person_links,
            get_visible_grave_site_person_links,
        )

    def test_selectors_have_exact_keyword_only_parameters(self) -> None:
        expectations = (
            (
                get_visible_person_grave_site_links,
                ("person", "actor"),
            ),
            (
                get_visible_grave_site_person_links,
                ("grave_site", "actor"),
            ),
        )

        for selector, expected_names in expectations:
            with self.subTest(selector=selector.__name__):
                parameters = signature(selector).parameters
                self.assertEqual(tuple(parameters), expected_names)
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in parameters.values()
                    )
                )

    def test_positional_arguments_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            get_visible_person_grave_site_links(
                object(),
                AnonymousUser(),
            )
        with self.assertRaises(TypeError):
            get_visible_grave_site_person_links(
                object(),
                AnonymousUser(),
            )


class VisiblePersonGraveSiteSelectorTests(TestCase):
    """Ověření autorizovaného čtení vazeb osob a hrobových míst."""

    person_error_message = (
        "Osoba musí být uložená a existovat v databázi."
    )
    grave_site_error_message = (
        "Hrobové nebo pamětní místo musí být uložené a existovat "
        "v databázi."
    )
    person_permission_message = (
        "Nemáte oprávnění zobrazit tuto osobu."
    )
    grave_site_permission_message = (
        "Nemáte oprávnění zobrazit toto hrobové nebo pamětní místo."
    )

    def setUp(self) -> None:
        self.person = self.create_person("Anna")
        self.other_person = self.create_person("Berta")
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.grave_site = self.create_grave_site(
            cemetery_name="Hřbitov A",
        )
        self.other_grave_site = self.create_grave_site(
            cemetery_name="Hřbitov B",
        )
        self.role = PersonGraveSiteRole.objects.get(code="buried")

    @staticmethod
    def create_user(username: str, **values: object):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def grant(self, actor, *codenames: str) -> None:
        actor.user_permissions.add(
            *(self.permission(codename) for codename in codenames)
        )

    @staticmethod
    def create_person(
        first_name: str,
        *,
        access_level: str = AccessLevel.PUBLIC,
        archived: bool = False,
        deleted: bool = False,
    ) -> Person:
        now = timezone.now()
        return Person.objects.create(
            first_name=first_name,
            last_name="Testovací",
            access_level=access_level,
            archived_at=now if archived else None,
            deleted_at=now if deleted else None,
        )

    @staticmethod
    def create_type(
        code: str,
        *,
        is_active: bool = True,
        is_system: bool = False,
    ) -> GraveSiteType:
        return GraveSiteType.objects.create(
            code=code,
            name=code,
            is_active=is_active,
            is_system=is_system,
        )

    @staticmethod
    def create_role(
        code: str,
        *,
        name: str | None = None,
        sort_order: int = 100,
        is_active: bool = True,
        is_system: bool = False,
    ) -> PersonGraveSiteRole:
        return PersonGraveSiteRole.objects.create(
            code=code,
            name=name or code,
            sort_order=sort_order,
            is_active=is_active,
            is_system=is_system,
        )

    def create_grave_site(self, **overrides: object) -> GraveSite:
        values = {
            "grave_site_type": self.grave_site_type,
            "location_text": "Základní lokalita",
        }
        values.update(overrides)
        return GraveSite.objects.create(**values)

    def create_link(self, **overrides: object) -> PersonGraveSite:
        values = {
            "person": self.person,
            "grave_site": self.grave_site,
            "role": self.role,
        }
        values.update(overrides)
        return PersonGraveSite.objects.create(**values)

    def visible_for_person(
        self,
        actor,
        *,
        person: Person | None = None,
    ) -> QuerySet[PersonGraveSite]:
        return get_visible_person_grave_site_links(
            person=person or self.person,
            actor=actor,
        )

    def visible_for_grave_site(
        self,
        actor,
        *,
        grave_site: GraveSite | None = None,
    ) -> QuerySet[PersonGraveSite]:
        return get_visible_grave_site_person_links(
            grave_site=grave_site or self.grave_site,
            actor=actor,
        )

    @staticmethod
    def assert_validation_error(
        context,
        *,
        key: str,
        code: str,
        message: str,
    ) -> None:
        error_dict = context.exception.error_dict
        if tuple(error_dict) != (key,):
            raise AssertionError(f"Neočekávané klíče chyb: {tuple(error_dict)}")
        error = error_dict[key][0]
        if error.code != code or error.message != message:
            raise AssertionError(
                f"Neočekávaná chyba: {error.code!r}, {error.message!r}"
            )

    def test_each_access_level_is_evaluated_once_per_selector_call(
        self,
    ) -> None:
        callbacks = (
            lambda: self.visible_for_person(AnonymousUser()),
            lambda: self.visible_for_grave_site(AnonymousUser()),
        )

        for callback in callbacks:
            with self.subTest(callback=callback):
                with patch(
                    "places.selectors.can_view_access_level",
                    wraps=selectors.can_view_access_level,
                ) as permission_check:
                    callback()

                self.assertEqual(permission_check.call_count, 4)
                self.assertEqual(
                    {
                        call.kwargs["access_level"]
                        for call in permission_check.call_args_list
                    },
                    set(AccessLevel.values),
                )

    def test_invalid_actor_uses_stable_contract_for_both_selectors(
        self,
    ) -> None:
        callbacks = (
            lambda actor: self.visible_for_person(actor),
            lambda actor: self.visible_for_grave_site(actor),
        )

        for callback in callbacks:
            for actor in (None, object()):
                with self.subTest(callback=callback, actor=actor):
                    with self.assertRaises(ValidationError) as context:
                        callback(actor)
                    self.assert_validation_error(
                        context,
                        key="actor",
                        code="actor_invalid",
                        message=(
                            "Actor není platným uživatelem ani anonymním "
                            "návštěvníkem."
                        ),
                    )

    def test_unsaved_and_missing_actor_use_stable_contract(
        self,
    ) -> None:
        unsaved = get_user_model()(username="unsaved-link-actor")
        missing = self.create_user("missing-link-actor")
        get_user_model().objects.filter(pk=missing.pk).delete()
        callbacks = (
            lambda actor: self.visible_for_person(actor),
            lambda actor: self.visible_for_grave_site(actor),
        )

        for callback in callbacks:
            for actor in (unsaved, missing):
                with self.subTest(
                    callback=callback,
                    actor=actor.username,
                ):
                    with self.assertRaises(ValidationError) as context:
                        callback(actor)
                    self.assert_validation_error(
                        context,
                        key="actor",
                        code="actor_unsaved",
                        message=(
                            "Přihlášený uživatel musí být uložený a "
                            "existovat v databázi."
                        ),
                    )

    def test_unsaved_and_missing_person_keep_permissionless_error(
        self,
    ) -> None:
        missing = self.create_person("Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for person in (Person(first_name="Neuložená"), missing):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    self.visible_for_person(
                        AnonymousUser(),
                        person=person,
                    )
                self.assert_validation_error(
                    context,
                    key="person",
                    code="person_unsaved",
                    message=self.person_error_message,
                )

    def test_unsaved_and_missing_grave_site_keep_permissionless_error(
        self,
    ) -> None:
        missing = self.create_grave_site(location_text="Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for grave_site in (
            GraveSite(grave_site_type=self.grave_site_type),
            missing,
        ):
            with self.subTest(grave_site=grave_site.pk):
                with self.assertRaises(ValidationError) as context:
                    self.visible_for_grave_site(
                        AnonymousUser(),
                        grave_site=grave_site,
                    )
                self.assert_validation_error(
                    context,
                    key="grave_site",
                    code="grave_site_unsaved",
                    message=self.grave_site_error_message,
                )

    def test_invisible_input_raises_but_invisible_row_is_filtered(
        self,
    ) -> None:
        hidden_person = self.create_person(
            "Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )
        hidden_site = self.create_grave_site(
            location_text="Skryté místo",
            access_level=AccessLevel.RESTRICTED,
        )
        hidden_link = self.create_link(
            grave_site=self.other_grave_site,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(grave_site=hidden_site)
        self.create_link(
            person=hidden_person,
            grave_site=self.grave_site,
        )

        with self.assertRaisesMessage(
            PermissionDenied,
            self.person_permission_message,
        ):
            self.visible_for_person(
                AnonymousUser(),
                person=hidden_person,
            )
        with self.assertRaisesMessage(
            PermissionDenied,
            self.grave_site_permission_message,
        ):
            self.visible_for_grave_site(
                AnonymousUser(),
                grave_site=hidden_site,
            )

        self.assertEqual(
            list(self.visible_for_person(AnonymousUser())),
            [],
        )
        self.assertEqual(
            list(self.visible_for_grave_site(AnonymousUser())),
            [],
        )
        self.assertNotIn(
            hidden_link,
            self.visible_for_person(AnonymousUser()),
        )

    def test_input_person_access_follows_central_policy(self) -> None:
        ordinary = self.create_user("input-person-ordinary")
        restricted = self.create_user("input-person-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("input-person-admin")
        self.grant(admin, "view_admin_only_content")
        staff = self.create_user("input-person-staff", is_staff=True)
        superuser = self.create_user(
            "input-person-super",
            is_superuser=True,
        )
        expectations = (
            (AnonymousUser(), AccessLevel.PUBLIC, True),
            (AnonymousUser(), AccessLevel.AUTHENTICATED, False),
            (ordinary, AccessLevel.AUTHENTICATED, True),
            (ordinary, AccessLevel.RESTRICTED, False),
            (restricted, AccessLevel.RESTRICTED, True),
            (restricted, AccessLevel.ADMIN_ONLY, False),
            (admin, AccessLevel.ADMIN_ONLY, True),
            (admin, AccessLevel.RESTRICTED, False),
            (staff, AccessLevel.RESTRICTED, False),
            (superuser, AccessLevel.ADMIN_ONLY, True),
        )

        for index, (actor, access_level, allowed) in enumerate(expectations):
            person = self.create_person(
                f"Vstupní osoba {index}",
                access_level=access_level,
            )
            with self.subTest(index=index):
                if allowed:
                    self.assertIsInstance(
                        self.visible_for_person(actor, person=person),
                        QuerySet,
                    )
                else:
                    with self.assertRaisesMessage(
                        PermissionDenied,
                        self.person_permission_message,
                    ):
                        self.visible_for_person(actor, person=person)

    def test_input_person_lifecycle_requires_independent_permissions(
        self,
    ) -> None:
        ordinary = self.create_user("input-lifecycle-ordinary")
        archived_actor = self.create_user("input-lifecycle-archived")
        self.grant(archived_actor, "view_archived_person")
        deleted_actor = self.create_user("input-lifecycle-deleted")
        self.grant(deleted_actor, "view_deleted_person")
        both_actor = self.create_user("input-lifecycle-both")
        self.grant(
            both_actor,
            "view_archived_person",
            "view_deleted_person",
        )
        superuser = self.create_user(
            "input-lifecycle-super",
            is_superuser=True,
        )
        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        both = self.create_person(
            "Archivovaná odstraněná",
            archived=True,
            deleted=True,
        )

        allowed = (
            (archived_actor, archived),
            (deleted_actor, deleted),
            (both_actor, both),
            (superuser, archived),
            (superuser, deleted),
            (superuser, both),
        )
        denied = (
            (ordinary, archived),
            (ordinary, deleted),
            (archived_actor, both),
            (deleted_actor, both),
        )

        for actor, person in allowed:
            with self.subTest(actor=actor.username, allowed=True):
                self.assertIsInstance(
                    self.visible_for_person(actor, person=person),
                    QuerySet,
                )
        for actor, person in denied:
            with self.subTest(actor=actor.username, allowed=False):
                with self.assertRaises(PermissionDenied):
                    self.visible_for_person(actor, person=person)

    def test_input_person_uses_fresh_database_state(self) -> None:
        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(AnonymousUser())

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(AnonymousUser())

        Person.objects.filter(pk=self.person.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(AnonymousUser())

    def test_input_grave_site_access_follows_central_policy(self) -> None:
        ordinary = self.create_user("input-site-ordinary")
        restricted = self.create_user("input-site-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("input-site-admin")
        self.grant(admin, "view_admin_only_content")
        staff = self.create_user("input-site-staff", is_staff=True)
        superuser = self.create_user(
            "input-site-super",
            is_superuser=True,
        )
        expectations = (
            (AnonymousUser(), AccessLevel.PUBLIC, True),
            (AnonymousUser(), AccessLevel.AUTHENTICATED, False),
            (ordinary, AccessLevel.AUTHENTICATED, True),
            (ordinary, AccessLevel.RESTRICTED, False),
            (restricted, AccessLevel.RESTRICTED, True),
            (restricted, AccessLevel.ADMIN_ONLY, False),
            (admin, AccessLevel.ADMIN_ONLY, True),
            (admin, AccessLevel.RESTRICTED, False),
            (staff, AccessLevel.RESTRICTED, False),
            (superuser, AccessLevel.ADMIN_ONLY, True),
        )

        for index, (actor, access_level, allowed) in enumerate(expectations):
            grave_site = self.create_grave_site(
                location_text=f"Vstupní místo {index}",
                access_level=access_level,
            )
            with self.subTest(index=index):
                if allowed:
                    self.assertIsInstance(
                        self.visible_for_grave_site(
                            actor,
                            grave_site=grave_site,
                        ),
                        QuerySet,
                    )
                else:
                    with self.assertRaisesMessage(
                        PermissionDenied,
                        self.grave_site_permission_message,
                    ):
                        self.visible_for_grave_site(
                            actor,
                            grave_site=grave_site,
                        )

    def test_input_grave_site_allows_archived_and_all_statuses(
        self,
    ) -> None:
        now = timezone.now()
        for status in GraveSiteStatus.values:
            grave_site = self.create_grave_site(
                location_text=status,
                status=status,
                archived_at=now,
            )
            with self.subTest(status=status):
                self.assertIsInstance(
                    self.visible_for_grave_site(
                        AnonymousUser(),
                        grave_site=grave_site,
                    ),
                    QuerySet,
                )

    def test_input_grave_site_rejects_deleted_even_for_superuser(
        self,
    ) -> None:
        deleted = self.create_grave_site(
            location_text="Odstraněné",
            deleted_at=timezone.now(),
        )
        superuser = self.create_user(
            "deleted-site-super",
            is_superuser=True,
        )

        for actor in (AnonymousUser(), superuser):
            with self.subTest(
                actor=getattr(actor, "username", "anonymous")
            ):
                with self.assertRaisesMessage(
                    PermissionDenied,
                    self.grave_site_permission_message,
                ):
                    self.visible_for_grave_site(
                        actor,
                        grave_site=deleted,
                    )

    def test_input_grave_site_uses_fresh_database_state(self) -> None:
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_grave_site(AnonymousUser())

        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        self.assertIsInstance(
            self.visible_for_grave_site(AnonymousUser()),
            QuerySet,
        )

        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_grave_site(AnonymousUser())

    def test_actor_permissions_and_flags_use_fresh_database_state(
        self,
    ) -> None:
        restricted_person = self.create_person(
            "Omezená osoba",
            access_level=AccessLevel.RESTRICTED,
        )
        actor = self.create_user("fresh-link-actor")
        current_actor = get_user_model().objects.get(pk=actor.pk)

        self.grant(current_actor, "view_restricted_content")
        self.assertIsInstance(
            self.visible_for_person(actor, person=restricted_person),
            QuerySet,
        )

        current_actor.user_permissions.remove(
            self.permission("view_restricted_content")
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(actor, person=restricted_person)

        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=True,
        )
        self.assertIsInstance(
            self.visible_for_person(actor, person=restricted_person),
            QuerySet,
        )

        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=False,
            is_active=False,
            is_staff=True,
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(actor, person=restricted_person)

    def test_lifecycle_permissions_use_fresh_actor_state(self) -> None:
        archived = self.create_person("Archivovaná", archived=True)
        actor = self.create_user("fresh-lifecycle-link-actor")
        current_actor = get_user_model().objects.get(pk=actor.pk)

        self.grant(current_actor, "view_archived_person")
        self.assertIsInstance(
            self.visible_for_person(actor, person=archived),
            QuerySet,
        )

        current_actor.user_permissions.remove(
            self.permission("view_archived_person")
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_person(actor, person=archived)

    def test_result_requires_visible_link_and_grave_site_for_person(
        self,
    ) -> None:
        visible = self.create_link()
        self.create_link(
            grave_site=self.other_grave_site,
            access_level=AccessLevel.RESTRICTED,
        )
        hidden_site = self.create_grave_site(
            location_text="Skrytá protistrana",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(grave_site=hidden_site)

        self.assertEqual(
            list(self.visible_for_person(AnonymousUser())),
            [visible],
        )

    def test_result_requires_visible_link_and_person_for_grave_site(
        self,
    ) -> None:
        visible = self.create_link()
        hidden_person = self.create_person(
            "Skrytá protistrana",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(person=hidden_person)
        self.create_link(
            person=self.other_person,
            access_level=AccessLevel.RESTRICTED,
        )

        self.assertEqual(
            list(self.visible_for_grave_site(AnonymousUser())),
            [visible],
        )

    def test_restricted_and_admin_only_permissions_remain_separate(
        self,
    ) -> None:
        public = self.create_link()
        restricted_link = self.create_link(
            grave_site=self.other_grave_site,
            access_level=AccessLevel.RESTRICTED,
        )
        third_site = self.create_grave_site(location_text="Třetí")
        admin_link = self.create_link(
            grave_site=third_site,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        restricted = self.create_user("result-link-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("result-link-admin")
        self.grant(admin, "view_admin_only_content")

        self.assertEqual(
            set(self.visible_for_person(restricted)),
            {public, restricted_link},
        )
        self.assertEqual(
            set(self.visible_for_person(admin)),
            {public, admin_link},
        )

    def test_result_person_lifecycle_uses_independent_permissions(
        self,
    ) -> None:
        regular = self.create_link()
        archived_person = self.create_person("Archivovaná", archived=True)
        deleted_person = self.create_person("Odstraněná", deleted=True)
        both_person = self.create_person(
            "Obojí",
            archived=True,
            deleted=True,
        )
        archived = self.create_link(person=archived_person)
        deleted = self.create_link(person=deleted_person)
        both = self.create_link(person=both_person)
        ordinary = self.create_user("result-lifecycle-ordinary")
        archived_actor = self.create_user("result-lifecycle-archived")
        self.grant(archived_actor, "view_archived_person")
        deleted_actor = self.create_user("result-lifecycle-deleted")
        self.grant(deleted_actor, "view_deleted_person")
        both_actor = self.create_user("result-lifecycle-both")
        self.grant(
            both_actor,
            "view_archived_person",
            "view_deleted_person",
        )

        expectations = (
            (ordinary, {regular}),
            (archived_actor, {regular, archived}),
            (deleted_actor, {regular, deleted}),
            (both_actor, {regular, archived, deleted, both}),
        )
        for actor, expected in expectations:
            with self.subTest(actor=actor.username):
                self.assertEqual(
                    set(self.visible_for_grave_site(actor)),
                    expected,
                )

    def test_result_grave_site_lifecycle_includes_archived_and_destroyed(
        self,
    ) -> None:
        regular = self.create_link()
        archived_site = self.create_grave_site(
            location_text="Archivované",
            archived_at=timezone.now(),
        )
        destroyed_site = self.create_grave_site(
            location_text="Zaniklé",
            status=GraveSiteStatus.DESTROYED,
        )
        deleted_site = self.create_grave_site(
            location_text="Odstraněné",
            deleted_at=timezone.now(),
        )
        archived = self.create_link(grave_site=archived_site)
        destroyed = self.create_link(grave_site=destroyed_site)
        self.create_link(grave_site=deleted_site)

        self.assertEqual(
            set(self.visible_for_person(AnonymousUser())),
            {regular, archived, destroyed},
        )

    def test_link_lifecycle_includes_archived_and_excludes_deleted(
        self,
    ) -> None:
        regular = self.create_link()
        archived = self.create_link()
        deleted = self.create_link()
        now = timezone.now()
        PersonGraveSite.objects.filter(pk=archived.pk).update(
            archived_at=now,
        )
        PersonGraveSite.objects.filter(pk=deleted.pk).update(
            deleted_at=now,
        )

        for result in (
            self.visible_for_person(AnonymousUser()),
            self.visible_for_grave_site(AnonymousUser()),
        ):
            with self.subTest(ordering=result.query.order_by):
                self.assertEqual(set(result), {regular, archived})

    def test_superuser_sees_all_access_and_person_lifecycle_but_not_deleted_site(
        self,
    ) -> None:
        superuser = self.create_user(
            "result-superuser",
            is_superuser=True,
        )
        visible = self.create_link(
            access_level=AccessLevel.ADMIN_ONLY,
        )
        archived_person = self.create_person(
            "Archivovaná",
            access_level=AccessLevel.ADMIN_ONLY,
            archived=True,
        )
        archived = self.create_link(
            person=archived_person,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        deleted_person = self.create_person(
            "Odstraněná",
            access_level=AccessLevel.RESTRICTED,
            deleted=True,
        )
        deleted = self.create_link(
            person=deleted_person,
            access_level=AccessLevel.RESTRICTED,
        )
        deleted_site = self.create_grave_site(
            location_text="Odstraněné",
            access_level=AccessLevel.ADMIN_ONLY,
            deleted_at=timezone.now(),
        )
        self.create_link(
            grave_site=deleted_site,
            access_level=AccessLevel.ADMIN_ONLY,
        )

        self.assertEqual(
            set(self.visible_for_grave_site(superuser)),
            {visible, archived, deleted},
        )
        with self.assertRaises(PermissionDenied):
            self.visible_for_grave_site(
                superuser,
                grave_site=deleted_site,
            )

    def test_inactive_privileged_user_follows_anonymous_policy(
        self,
    ) -> None:
        public = self.create_link()
        self.create_link(
            grave_site=self.other_grave_site,
            access_level=AccessLevel.AUTHENTICATED,
        )
        restricted_person = self.create_person(
            "Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(person=restricted_person)
        archived_person = self.create_person("Archivovaná", archived=True)
        self.create_link(person=archived_person)
        inactive = self.create_user(
            "inactive-privileged-link",
            is_active=False,
            is_staff=True,
            is_superuser=True,
        )
        inactive.groups.add(Group.objects.get(name="Správce"))

        self.assertEqual(
            list(self.visible_for_person(inactive)),
            [public],
        )
        self.assertEqual(
            list(self.visible_for_grave_site(inactive)),
            [public],
        )

    def test_status_type_role_and_verification_do_not_filter_rows(
        self,
    ) -> None:
        inactive_type = self.create_type(
            "visible_inactive_type",
            is_active=False,
        )
        user_type = self.create_type("visible_user_type")
        inactive_role = self.create_role(
            "visible_inactive_role",
            is_active=False,
        )
        user_role = self.create_role("visible_user_role")
        expected = set()
        for index, verification_status in enumerate(
            VerificationStatus.values
        ):
            grave_site = self.create_grave_site(
                grave_site_type=(
                    inactive_type if index % 2 == 0 else user_type
                ),
                status=(
                    GraveSiteStatus.DESTROYED
                    if index % 2 == 0
                    else GraveSiteStatus.UNKNOWN
                ),
                location_text=f"Historické {index}",
                verification_status=verification_status,
            )
            expected.add(
                self.create_link(
                    grave_site=grave_site,
                    role=inactive_role if index % 2 == 0 else user_role,
                    verification_status=verification_status,
                )
            )

        with patch.object(
            PersonGraveSite,
            "full_clean",
            side_effect=AssertionError("Selector nesmí validovat model."),
        ):
            self.assertEqual(
                set(self.visible_for_person(AnonymousUser())),
                expected,
            )

    def test_place_is_not_authorized_separately(self) -> None:
        place = Place.objects.create(
            name="Soukromé historické místo",
            normalized_name="soukrome historicke misto",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        Place.objects.filter(pk=place.pk).update(
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        grave_site = self.create_grave_site(
            place=place,
            location_text="Veřejné hrobové místo",
        )
        link = self.create_link(grave_site=grave_site)

        result = list(self.visible_for_person(AnonymousUser()))

        self.assertEqual(result, [link])
        self.assertEqual(result[0].grave_site.place_id, place.pk)

    def test_legitimate_duplicates_are_preserved(self) -> None:
        first = self.create_link()
        second = self.create_link()

        for queryset in (
            self.visible_for_person(AnonymousUser()),
            self.visible_for_grave_site(AnonymousUser()),
        ):
            with self.subTest(ordering=queryset.query.order_by):
                self.assertFalse(queryset.query.distinct)
                self.assertEqual(list(queryset), [first, second])

    def test_exact_permissionless_ordering_is_preserved(self) -> None:
        person_queryset = self.visible_for_person(AnonymousUser())
        site_queryset = self.visible_for_grave_site(AnonymousUser())

        self.assertEqual(
            person_queryset.query.order_by,
            (
                "grave_site__cemetery_name",
                "grave_site__section",
                "grave_site__row",
                "grave_site__grave_number",
                "grave_site_id",
                "role__sort_order",
                "role__name",
                "pk",
            ),
        )
        self.assertEqual(
            site_queryset.query.order_by,
            (
                "person_id",
                "role__sort_order",
                "role__name",
                "pk",
            ),
        )

    def test_filtering_preserves_materialized_permissionless_order(
        self,
    ) -> None:
        first_site = self.create_grave_site(
            cemetery_name="A",
            location_text="První",
        )
        hidden_site = self.create_grave_site(
            cemetery_name="B",
            location_text="Skryté",
        )
        last_site = self.create_grave_site(
            cemetery_name="C",
            location_text="Poslední",
        )
        first = self.create_link(grave_site=first_site)
        self.create_link(
            grave_site=hidden_site,
            access_level=AccessLevel.RESTRICTED,
        )
        last = self.create_link(grave_site=last_site)

        permissionless = list(
            get_person_grave_site_links(person=self.person)
        )
        visible = list(self.visible_for_person(AnonymousUser()))

        self.assertEqual(visible, [first, last])
        self.assertEqual(
            visible,
            [
                link
                for link in permissionless
                if link.access_level == AccessLevel.PUBLIC
            ],
        )

    def test_result_is_lazy_and_select_related_avoids_n_plus_one(
        self,
    ) -> None:
        creator = self.create_user("visible-link-creator")
        for index in range(8):
            grave_site = self.create_grave_site(
                cemetery_name=f"Hřbitov {index}",
                created_by=creator,
            )
            self.create_link(
                grave_site=grave_site,
                created_by=creator,
            )

        with self.assertNumQueries(2):
            queryset = self.visible_for_person(AnonymousUser())

        self.assertIsInstance(queryset, QuerySet)
        self.assertIs(queryset.model, PersonGraveSite)
        self.assertEqual(queryset._prefetch_related_lookups, ())
        with self.assertNumQueries(1):
            result = list(queryset)
            for link in result:
                str(link.person)
                str(link.grave_site)
                str(link.grave_site.grave_site_type)
                str(link.grave_site.place)
                str(link.role)
                str(link.created_by)

        self.assertEqual(len(result), 8)

    def test_query_profile_is_constant_for_small_and_large_results(
        self,
    ) -> None:
        self.create_link()
        with CaptureQueriesContext(connection) as small_context:
            list(self.visible_for_person(AnonymousUser()))

        for index in range(12):
            grave_site = self.create_grave_site(
                cemetery_name=f"Další {index}",
            )
            self.create_link(grave_site=grave_site)
        with CaptureQueriesContext(connection) as large_context:
            result = list(self.visible_for_person(AnonymousUser()))

        self.assertEqual(len(small_context), 3)
        self.assertEqual(len(small_context), len(large_context))
        self.assertEqual(len(result), 13)

    def test_grave_site_selector_is_lazy_with_constant_query_profile(
        self,
    ) -> None:
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            place=self.place,
        )
        self.create_link()
        with CaptureQueriesContext(connection) as small_context:
            small = list(self.visible_for_grave_site(AnonymousUser()))
            for link in small:
                str(link.person)
                str(link.grave_site)
                str(link.grave_site.grave_site_type)
                str(link.grave_site.place)
                str(link.role)
                str(link.created_by)

        for index in range(12):
            person = self.create_person(f"Další osoba {index}")
            self.create_link(person=person)
        with CaptureQueriesContext(connection) as large_context:
            large = list(self.visible_for_grave_site(AnonymousUser()))
            for link in large:
                str(link.person)
                str(link.grave_site)
                str(link.grave_site.grave_site_type)
                str(link.grave_site.place)
                str(link.role)
                str(link.created_by)

        self.assertEqual(len(small_context), 3)
        self.assertEqual(len(small_context), len(large_context))
        self.assertEqual(len(small), 1)
        self.assertEqual(len(large), 13)

    def test_permissionless_selectors_remain_unfiltered(self) -> None:
        restricted = self.create_link(
            access_level=AccessLevel.RESTRICTED,
        )
        deleted_person = self.create_person(
            "Odstraněná",
            deleted=True,
        )
        deleted_person_link = self.create_link(person=deleted_person)
        deleted_site = self.create_grave_site(
            location_text="Odstraněné",
            deleted_at=timezone.now(),
        )
        deleted_site_link = self.create_link(grave_site=deleted_site)

        with patch(
            "places.selectors.can_view_access_level"
        ) as permission_policy:
            person_result = list(
                get_person_grave_site_links(person=self.person)
            )
            site_result = list(
                get_grave_site_person_links(grave_site=self.grave_site)
            )

        permission_policy.assert_not_called()
        self.assertEqual(
            set(person_result),
            {restricted, deleted_site_link},
        )
        self.assertEqual(
            set(site_result),
            {restricted, deleted_person_link},
        )

    def test_permissionless_selectors_receive_fresh_input_objects(
        self,
    ) -> None:
        Person.objects.filter(pk=self.person.pk).update(
            last_name="Aktuální osoba",
        )
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            location_text="Aktuální místo",
        )

        with patch(
            "places.selectors.get_person_grave_site_links",
            wraps=get_person_grave_site_links,
        ) as person_permissionless:
            self.visible_for_person(AnonymousUser())
        with patch(
            "places.selectors.get_grave_site_person_links",
            wraps=get_grave_site_person_links,
        ) as site_permissionless:
            self.visible_for_grave_site(AnonymousUser())

        called_person = person_permissionless.call_args.kwargs["person"]
        called_site = site_permissionless.call_args.kwargs["grave_site"]
        self.assertEqual(called_person.last_name, "Aktuální osoba")
        self.assertEqual(called_site.location_text, "Aktuální místo")
        self.assertIsNot(called_person, self.person)
        self.assertIsNot(called_site, self.grave_site)

    def test_selectors_perform_no_writes_or_input_changes(self) -> None:
        link = self.create_link()
        actor = self.create_user("visible-link-no-writes")
        person_state = self.person.__dict__.copy()
        grave_site_state = self.grave_site.__dict__.copy()
        actor_state = actor.__dict__.copy()
        link_values = PersonGraveSite.objects.values_list(
            "person_id",
            "grave_site_id",
            "role_id",
            "updated_at",
        ).get(pk=link.pk)
        counts = (
            Person.objects.count(),
            GraveSite.objects.count(),
            PersonGraveSite.objects.count(),
            PersonGraveSiteRole.objects.count(),
            Place.objects.count(),
        )

        list(self.visible_for_person(actor))
        list(self.visible_for_grave_site(actor))

        self.assertEqual(
            (
                Person.objects.count(),
                GraveSite.objects.count(),
                PersonGraveSite.objects.count(),
                PersonGraveSiteRole.objects.count(),
                Place.objects.count(),
            ),
            counts,
        )
        self.assertEqual(self.person.__dict__, person_state)
        self.assertEqual(self.grave_site.__dict__, grave_site_state)
        self.assertEqual(actor.__dict__, actor_state)
        self.assertEqual(
            PersonGraveSite.objects.values_list(
                "person_id",
                "grave_site_id",
                "role_id",
                "updated_at",
            ).get(pk=link.pk),
            link_values,
        )
