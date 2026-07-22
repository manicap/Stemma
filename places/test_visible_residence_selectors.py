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

from common.choices import AccessLevel, DatePrecision, VerificationStatus
from people.models import Person

from . import selectors
from .models import Place, Residence, ResidenceType
from .selectors import (
    get_person_residences,
    get_visible_person_residences,
)


class VisibleResidenceSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu autorizovaného selectoru."""

    def test_parameters_are_exactly_keyword_only_person_and_actor(self) -> None:
        parameters = signature(get_visible_person_residences).parameters

        self.assertEqual(tuple(parameters), ("person", "actor"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class VisibleResidenceSelectorTests(TestCase):
    """Ověření oprávněného čtení úplné historie bydlišť osoby."""

    def setUp(self) -> None:
        self.person = self.create_person("Anna")
        self.residence_type = ResidenceType.objects.create(
            code="visible_primary",
            name="Hlavní",
            sort_order=10,
            is_system=True,
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )

    def create_user(self, username: str, **values: object):
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

    def create_residence(self, **overrides: object) -> Residence:
        values = {
            "person": self.person,
            "residence_type": self.residence_type,
            "place": self.place,
        }
        values.update(overrides)
        residence = Residence(**values)
        residence.full_clean()
        residence.save()
        return residence

    def visible(self, actor, *, person: Person | None = None) -> QuerySet:
        return get_visible_person_residences(
            person=person or self.person,
            actor=actor,
        )

    def assert_error_code(
        self,
        *,
        person: Person,
        actor,
        key: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            get_visible_person_residences(person=person, actor=actor)

        self.assertEqual(context.exception.error_dict[key][0].code, code)

    def test_each_access_level_is_evaluated_once(self) -> None:
        with patch(
            "places.selectors.can_view_access_level",
            wraps=selectors.can_view_access_level,
        ) as permission_check:
            self.visible(AnonymousUser())

        self.assertEqual(permission_check.call_count, 4)
        self.assertEqual(
            {
                call.kwargs["access_level"]
                for call in permission_check.call_args_list
            },
            set(AccessLevel.values),
        )

    def test_invalid_actor_uses_stable_errors(self) -> None:
        for actor in (None, object()):
            with self.subTest(actor=actor):
                self.assert_error_code(
                    person=self.person,
                    actor=actor,
                    key="actor",
                    code="actor_invalid",
                )

        unsaved = get_user_model()(username="unsaved")
        missing = self.create_user("missing")
        get_user_model().objects.filter(pk=missing.pk).delete()
        for actor in (unsaved, missing):
            with self.subTest(actor=actor.username):
                self.assert_error_code(
                    person=self.person,
                    actor=actor,
                    key="actor",
                    code="actor_unsaved",
                )

    def test_invalid_person_uses_permissionless_error_contract(self) -> None:
        missing = self.create_person("Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for person in (Person(first_name="Neuložená"), missing):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    self.visible(AnonymousUser(), person=person)

                error = context.exception.error_dict["person"][0]
                self.assertEqual(error.code, "person_unsaved")
                self.assertEqual(
                    error.message,
                    "Osoba musí být uložená a existovat v databázi.",
                )

    def test_input_access_levels_follow_central_actor_policy(self) -> None:
        ordinary = self.create_user("ordinary")
        restricted = self.create_user("restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("admin")
        self.grant(admin, "view_admin_only_content")
        staff = self.create_user("staff", is_staff=True)
        superuser = self.create_user("super", is_superuser=True)
        inactive = self.create_user("inactive", is_active=False)
        expectations = (
            (AnonymousUser(), AccessLevel.PUBLIC, True),
            (AnonymousUser(), AccessLevel.AUTHENTICATED, False),
            (AnonymousUser(), AccessLevel.RESTRICTED, False),
            (AnonymousUser(), AccessLevel.ADMIN_ONLY, False),
            (ordinary, AccessLevel.PUBLIC, True),
            (ordinary, AccessLevel.AUTHENTICATED, True),
            (ordinary, AccessLevel.RESTRICTED, False),
            (ordinary, AccessLevel.ADMIN_ONLY, False),
            (restricted, AccessLevel.RESTRICTED, True),
            (admin, AccessLevel.ADMIN_ONLY, True),
            (staff, AccessLevel.RESTRICTED, False),
            (superuser, AccessLevel.ADMIN_ONLY, True),
            (inactive, AccessLevel.PUBLIC, True),
            (inactive, AccessLevel.AUTHENTICATED, False),
        )

        for index, (actor, access_level, allowed) in enumerate(expectations):
            with self.subTest(index=index):
                person = self.create_person(
                    f"Vstup {index}",
                    access_level=access_level,
                )
                if allowed:
                    self.assertIsInstance(
                        self.visible(actor, person=person),
                        QuerySet,
                    )
                else:
                    with self.assertRaisesMessage(
                        PermissionDenied,
                        "Nemáte oprávnění zobrazit tuto osobu.",
                    ):
                        self.visible(actor, person=person)

    def test_input_lifecycle_requires_each_person_permission(self) -> None:
        ordinary = self.create_user("lifecycle-ordinary")
        archived_actor = self.create_user("lifecycle-archived")
        self.grant(archived_actor, "view_archived_person")
        deleted_actor = self.create_user("lifecycle-deleted")
        self.grant(deleted_actor, "view_deleted_person")
        both_actor = self.create_user("lifecycle-both")
        self.grant(
            both_actor,
            "view_archived_person",
            "view_deleted_person",
        )
        staff = self.create_user("lifecycle-staff", is_staff=True)
        superuser = self.create_user("lifecycle-super", is_superuser=True)
        inactive_manager = self.create_user(
            "lifecycle-inactive-manager",
            is_active=False,
        )
        inactive_manager.groups.add(Group.objects.get(name="Správce"))
        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        both = self.create_person("Obojí", archived=True, deleted=True)

        for actor, person in (
            (archived_actor, archived),
            (deleted_actor, deleted),
            (both_actor, both),
            (superuser, archived),
            (superuser, deleted),
            (superuser, both),
        ):
            with self.subTest(actor=actor.username, person=person.first_name):
                self.assertIsInstance(
                    self.visible(actor, person=person),
                    QuerySet,
                )

        for actor, person in (
            (ordinary, archived),
            (ordinary, deleted),
            (archived_actor, both),
            (deleted_actor, both),
            (staff, archived),
            (inactive_manager, archived),
        ):
            with self.subTest(actor=actor.username, person=person.first_name):
                with self.assertRaises(PermissionDenied):
                    self.visible(actor, person=person)

    def test_input_person_uses_current_database_state(self) -> None:
        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )

        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

        Person.objects.filter(pk=self.person.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

    def test_actor_permissions_and_state_use_current_database_state(self) -> None:
        restricted_person = self.create_person(
            "Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        actor = self.create_user("stale-access")
        actor.has_perm("accounts.view_restricted_content")
        current_actor = get_user_model().objects.get(pk=actor.pk)
        self.grant(current_actor, "view_restricted_content")
        self.assertIsInstance(
            self.visible(actor, person=restricted_person),
            QuerySet,
        )

        current_actor.user_permissions.remove(
            self.permission("view_restricted_content")
        )
        with self.assertRaises(PermissionDenied):
            self.visible(actor, person=restricted_person)

        get_user_model().objects.filter(pk=actor.pk).update(is_superuser=True)
        self.assertIsInstance(
            self.visible(actor, person=restricted_person),
            QuerySet,
        )
        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=False,
            is_active=False,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(actor, person=restricted_person)

    def test_lifecycle_permissions_use_current_actor_state(self) -> None:
        archived = self.create_person("Archivovaná", archived=True)
        actor = self.create_user("stale-lifecycle")
        actor.has_perm("people.view_archived_person")
        current_actor = get_user_model().objects.get(pk=actor.pk)
        self.grant(current_actor, "view_archived_person")

        self.assertIsInstance(
            self.visible(actor, person=archived),
            QuerySet,
        )
        current_actor.user_permissions.remove(
            self.permission("view_archived_person")
        )
        with self.assertRaises(PermissionDenied):
            self.visible(actor, person=archived)

    def test_residence_access_levels_are_filtered_in_database(self) -> None:
        residences = {
            level: self.create_residence(
                access_level=level,
                address_text=level,
            )
            for level in AccessLevel.values
        }
        ordinary = self.create_user("result-ordinary")
        restricted = self.create_user("result-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("result-admin")
        self.grant(admin, "view_admin_only_content")
        both = self.create_user("result-both")
        self.grant(
            both,
            "view_restricted_content",
            "view_admin_only_content",
        )
        staff = self.create_user("result-staff", is_staff=True)
        inactive = self.create_user("result-inactive", is_active=False)
        superuser = self.create_user("result-super", is_superuser=True)
        expectations = (
            (AnonymousUser(), {AccessLevel.PUBLIC}),
            (
                ordinary,
                {AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED},
            ),
            (
                restricted,
                {
                    AccessLevel.PUBLIC,
                    AccessLevel.AUTHENTICATED,
                    AccessLevel.RESTRICTED,
                },
            ),
            (
                admin,
                {
                    AccessLevel.PUBLIC,
                    AccessLevel.AUTHENTICATED,
                    AccessLevel.ADMIN_ONLY,
                },
            ),
            (both, set(AccessLevel.values)),
            (staff, {AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED}),
            (inactive, {AccessLevel.PUBLIC}),
            (superuser, set(AccessLevel.values)),
        )

        for actor, expected_levels in expectations:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                result = list(self.visible(actor))
                self.assertEqual(
                    {residence.pk for residence in result},
                    {
                        residences[level].pk
                        for level in expected_levels
                    },
                )

    def test_residence_lifecycle_only_excludes_soft_deleted_rows(self) -> None:
        regular = self.create_residence(address_text="Běžné")
        archived = self.create_residence(address_text="Archivované")
        deleted = self.create_residence(address_text="Odstraněné")
        now = timezone.now()
        Residence.objects.filter(pk=archived.pk).update(archived_at=now)
        Residence.objects.filter(pk=deleted.pk).update(deleted_at=now)

        superuser = self.create_user("lifecycle-result-super", is_superuser=True)
        for actor in (AnonymousUser(), superuser):
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                self.assertEqual(
                    list(self.visible(actor)),
                    [regular, archived],
                )

    def test_no_other_residence_dimensions_are_filtered(self) -> None:
        inactive_type = ResidenceType.objects.create(
            code="visible_inactive",
            name="Neaktivní uživatelský",
            is_active=False,
        )
        place = Place.objects.create(
            name="Historické místo",
            normalized_name="historicke misto",
        )
        Place.objects.filter(pk=place.pk).update(
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        unknown = self.create_residence(
            address_text="Neznámé",
            verification_status=VerificationStatus.UNCONFIRMED,
        )
        partial = self.create_residence(
            address_text="Částečné",
            verification_status=VerificationStatus.VERIFIED,
            date_precision=DatePrecision.YEAR,
            start_year=1850,
        )
        historical = self.create_residence(
            address_text="Historické",
            verification_status=VerificationStatus.PROBABLE,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1910,
        )
        future = self.create_residence(
            residence_type=inactive_type,
            place=place,
            verification_status=VerificationStatus.DISPUTED,
            date_precision=DatePrecision.RANGE,
            start_year=2100,
            end_year=2110,
        )

        self.assertEqual(
            set(self.visible(AnonymousUser())),
            {unknown, partial, historical, future},
        )

    def test_calls_permissionless_selector_with_fresh_person(self) -> None:
        original_state = self.person.__dict__.copy()
        Person.objects.filter(pk=self.person.pk).update(last_name="Aktuální")

        with patch(
            "places.selectors.get_person_residences",
            wraps=get_person_residences,
        ) as permissionless:
            result = self.visible(AnonymousUser())

        called_person = permissionless.call_args.kwargs["person"]
        self.assertEqual(called_person.last_name, "Aktuální")
        self.assertIsNot(called_person, self.person)
        self.assertEqual(self.person.__dict__, original_state)
        self.assertIsInstance(result, QuerySet)

    def test_preserves_permissionless_order_after_filtering(self) -> None:
        public_unknown = self.create_residence(address_text="Neznámé")
        self.create_residence(
            address_text="Skryté",
            access_level=AccessLevel.RESTRICTED,
            date_precision=DatePrecision.YEAR,
            start_year=1800,
        )
        public_late = self.create_residence(
            address_text="Pozdější",
            date_precision=DatePrecision.YEAR,
            start_year=1900,
        )
        permissionless = list(get_person_residences(person=self.person))

        result = list(self.visible(AnonymousUser()))

        self.assertEqual(result, [public_unknown, public_late])
        self.assertEqual(
            result,
            [
                residence
                for residence in permissionless
                if residence.access_level == AccessLevel.PUBLIC
            ],
        )

    def test_result_is_lazy_and_select_related_avoids_n_plus_one(self) -> None:
        creator = self.create_user("creator")
        self.create_residence(
            address_text="Adresa 0",
            created_by=creator,
        )
        one_queryset = self.visible(AnonymousUser())
        with self.assertNumQueries(1):
            one_result = list(one_queryset)
            str(one_result[0].person)
            str(one_result[0].residence_type)
            str(one_result[0].place)
            str(one_result[0].created_by)

        for index in range(1, 8):
            self.create_residence(
                address_text=f"Adresa {index}",
                created_by=creator,
            )

        with self.assertNumQueries(2):
            queryset = self.visible(AnonymousUser())

        self.assertIsInstance(queryset, QuerySet)
        self.assertIs(queryset.model, Residence)
        with self.assertNumQueries(1):
            result = list(queryset)
            for residence in result:
                str(residence.person)
                str(residence.residence_type)
                str(residence.place)
                str(residence.created_by)
        self.assertEqual(len(result), 8)

    def test_query_count_is_constant_for_small_and_large_results(self) -> None:
        self.create_residence(address_text="První")
        with CaptureQueriesContext(connection) as small_context:
            list(self.visible(AnonymousUser()))

        for index in range(12):
            self.create_residence(address_text=f"Další {index}")
        with CaptureQueriesContext(connection) as large_context:
            result = list(self.visible(AnonymousUser()))

        self.assertEqual(len(small_context), 3)
        self.assertEqual(len(small_context), len(large_context))
        self.assertEqual(len(result), 13)

    def test_selector_performs_no_writes_or_input_instance_changes(self) -> None:
        public = self.create_residence(address_text="Veřejné")
        restricted = self.create_residence(
            address_text="Omezené",
            access_level=AccessLevel.RESTRICTED,
        )
        permissionless = list(get_person_residences(person=self.person))
        person_state = self.person.__dict__.copy()
        residence_state = {
            residence.pk: residence.__dict__.copy()
            for residence in permissionless
        }
        residence_count = Residence.objects.count()
        actor = self.create_user("no-writes-actor")
        actor_state = actor.__dict__.copy()
        person_count = Person.objects.count()
        type_count = ResidenceType.objects.count()
        place_count = Place.objects.count()
        type_state = self.residence_type.__dict__.copy()
        place_state = self.place.__dict__.copy()

        self.assertEqual(list(self.visible(actor)), [public])

        self.assertEqual(Residence.objects.count(), residence_count)
        self.assertEqual(Person.objects.count(), person_count)
        self.assertEqual(ResidenceType.objects.count(), type_count)
        self.assertEqual(Place.objects.count(), place_count)
        self.assertEqual(self.person.__dict__, person_state)
        self.assertEqual(actor.__dict__, actor_state)
        self.assertEqual(self.residence_type.__dict__, type_state)
        self.assertEqual(self.place.__dict__, place_state)
        self.assertEqual(
            {residence.pk: residence.__dict__ for residence in permissionless},
            residence_state,
        )
        self.assertEqual(permissionless, [public, restricted])
