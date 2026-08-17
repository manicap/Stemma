from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision

from . import selectors
from .models import Person, Relationship, RelationshipType
from .selectors import (
    RelationshipOverviewItem,
    RelationshipOverviewReason,
    get_relationship_overview,
    get_visible_relationship_overview,
)


class VisibleRelationshipOverviewApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu autorizovaného selectoru."""

    def test_public_api_and_keyword_only_parameters_are_exact(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "RelationshipOverviewItem",
                "RelationshipOverviewReason",
                "SiblingOverviewItem",
                "get_biological_siblings",
                "get_relationship_overview",
                "get_sibling_overview",
                "get_visible_people",
                "get_visible_person",
                "get_visible_relationship_overview",
            ),
        )
        parameters = signature(
            get_visible_relationship_overview
        ).parameters
        self.assertEqual(tuple(parameters), ("person", "actor"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class VisibleRelationshipOverviewSelectorTests(TestCase):
    """Ověření filtrování osob, provenance a biologických cest."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.relationship_types = {
            relationship_type.code: relationship_type
            for relationship_type in RelationshipType.objects.all()
        }

    def setUp(self) -> None:
        self.relationship_year = 1800

    def create_user(self, username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    def permission(self, codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def grant(self, actor, *codenames: str) -> None:
        actor.user_permissions.add(
            *(self.permission(codename) for codename in codenames)
        )

    def create_person(
        self,
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

    def create_relationship(
        self,
        code: str,
        person_a: Person,
        person_b: Person,
        *,
        access_level: str = AccessLevel.PUBLIC,
        archived: bool = False,
        deleted: bool = False,
    ) -> Relationship:
        self.relationship_year += 1
        now = timezone.now()
        return Relationship.objects.create(
            relationship_type=self.relationship_types[code],
            person_a=person_a,
            person_b=person_b,
            access_level=access_level,
            archived_at=now if archived else None,
            deleted_at=now if deleted else None,
            date_precision=DatePrecision.YEAR,
            start_year=self.relationship_year,
        )

    def item_for(self, result, person: Person):
        return next(
            (item for item in result if item.person.pk == person.pk),
            None,
        )

    def visible(
        self,
        person: Person,
        actor,
    ) -> tuple[RelationshipOverviewItem, ...]:
        return get_visible_relationship_overview(
            person=person,
            actor=actor,
        )

    def make_biological_path(
        self,
        *,
        person: Person,
        sibling: Person,
        parent: Person,
        input_edge_access: str = AccessLevel.PUBLIC,
        sibling_edge_access: str = AccessLevel.PUBLIC,
        archived_edges: bool = False,
    ) -> tuple[Relationship, Relationship]:
        return (
            self.create_relationship(
                "biological_parent",
                parent,
                person,
                access_level=input_edge_access,
                archived=archived_edges,
            ),
            self.create_relationship(
                "biological_parent",
                parent,
                sibling,
                access_level=sibling_edge_access,
                archived=archived_edges,
            ),
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
            self.visible(person, actor)
        self.assertEqual(context.exception.error_dict[key][0].code, code)

    def test_returns_existing_frozen_read_model_as_tuple(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        self.create_relationship("partner", person, other)

        result = self.visible(person, AnonymousUser())

        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[0], RelationshipOverviewItem)
        self.assertIsInstance(
            result[0].reasons[0],
            RelationshipOverviewReason,
        )

    def test_each_access_level_is_evaluated_once(self) -> None:
        person = self.create_person("Vstup")

        with patch(
            "people.selectors.can_view_access_level",
            wraps=selectors.can_view_access_level,
        ) as permission_check:
            self.visible(person, AnonymousUser())

        self.assertEqual(permission_check.call_count, 4)
        self.assertEqual(
            {
                call.kwargs["access_level"]
                for call in permission_check.call_args_list
            },
            set(AccessLevel.values),
        )

    def test_invalid_person_and_actor_use_stable_errors(self) -> None:
        missing = self.create_person("Chybějící")
        Person.objects.filter(pk=missing.pk).delete()
        for person in (Person(first_name="Neuložená"), missing):
            with self.subTest(person=person.first_name):
                self.assert_error_code(
                    person=person,
                    actor=AnonymousUser(),
                    key="person",
                    code="person_unsaved",
                )

        person = self.create_person("Platná")
        for actor in (None, object()):
            with self.subTest(actor=actor):
                self.assert_error_code(
                    person=person,
                    actor=actor,
                    key="actor",
                    code="actor_invalid",
                )

        unsaved_actor = get_user_model()(username="unsaved")
        missing_actor = self.create_user("missing")
        get_user_model().objects.filter(pk=missing_actor.pk).delete()
        for actor in (unsaved_actor, missing_actor):
            with self.subTest(actor=actor.username):
                self.assert_error_code(
                    person=person,
                    actor=actor,
                    key="actor",
                    code="actor_unsaved",
                )

    def test_input_access_levels_follow_actor_policy(self) -> None:
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
                    self.assertEqual(self.visible(person, actor), ())
                else:
                    with self.assertRaisesMessage(
                        PermissionDenied,
                        "Nemáte oprávnění zobrazit tuto osobu.",
                    ):
                        self.visible(person, actor)

    def test_input_lifecycle_requires_each_permission(self) -> None:
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
        superuser = self.create_user(
            "lifecycle-superuser",
            is_superuser=True,
        )

        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        both = self.create_person(
            "Obojí",
            archived=True,
            deleted=True,
        )
        allowed = (
            (archived_actor, archived),
            (deleted_actor, deleted),
            (both_actor, both),
            (superuser, archived),
            (superuser, deleted),
        )
        for actor, person in allowed:
            with self.subTest(actor=actor.username, person=person.first_name):
                self.assertEqual(self.visible(person, actor), ())

        denied = (
            (ordinary, archived),
            (ordinary, deleted),
            (archived_actor, both),
            (deleted_actor, both),
            (staff, archived),
        )
        for actor, person in denied:
            with self.subTest(actor=actor.username, person=person.first_name):
                with self.assertRaises(PermissionDenied):
                    self.visible(person, actor)

    def test_input_person_uses_current_database_state(self) -> None:
        person = self.create_person("Původně veřejná")
        Person.objects.filter(pk=person.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )

        with self.assertRaises(PermissionDenied):
            self.visible(person, AnonymousUser())

    def test_lifecycle_permissions_use_current_actor_state(self) -> None:
        person = self.create_person("Archivovaná", archived=True)
        actor = self.create_user("stale-lifecycle")
        actor.has_perm("people.view_archived_person")
        current_actor = get_user_model().objects.get(pk=actor.pk)
        self.grant(current_actor, "view_archived_person")

        self.assertEqual(self.visible(person, actor), ())

        current_actor.user_permissions.remove(
            self.permission("view_archived_person")
        )
        with self.assertRaises(PermissionDenied):
            self.visible(person, actor)

    def test_result_people_are_filtered_by_access_level(self) -> None:
        person = self.create_person("Vstup")
        people = {
            access_level: self.create_person(
                access_level,
                access_level=access_level,
            )
            for access_level in (
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.RESTRICTED,
                AccessLevel.ADMIN_ONLY,
            )
        }
        for other in people.values():
            self.create_relationship("partner", person, other)

        ordinary = self.create_user("result-ordinary")
        restricted = self.create_user("result-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("result-admin")
        self.grant(admin, "view_admin_only_content")
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
            (superuser, set(people)),
        )
        for actor, expected_levels in expectations:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                result_ids = {
                    item.person.pk for item in self.visible(person, actor)
                }
                self.assertEqual(
                    result_ids,
                    {people[level].pk for level in expected_levels},
                )

    def test_archived_and_deleted_result_people_follow_contract(self) -> None:
        person = self.create_person("Vstup")
        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        self.create_relationship("partner", person, archived)
        self.create_relationship("partner", person, deleted)
        lifecycle_actor = self.create_user("lifecycle-result")
        self.grant(
            lifecycle_actor,
            "view_archived_person",
            "view_deleted_person",
        )
        staff = self.create_user("result-staff", is_staff=True)
        superuser = self.create_user("result-superuser", is_superuser=True)

        self.assertIsNone(self.item_for(self.visible(person, staff), archived))
        self.assertIsNotNone(
            self.item_for(self.visible(person, lifecycle_actor), archived)
        )
        self.assertIsNotNone(
            self.item_for(self.visible(person, superuser), archived)
        )
        for actor in (lifecycle_actor, superuser):
            self.assertIsNone(
                self.item_for(self.visible(person, actor), deleted)
            )

    def test_explicit_reasons_are_filtered_by_access_level(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        relationships = {
            level: self.create_relationship(
                "partner",
                person,
                other,
                access_level=level,
            )
            for level in (
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.RESTRICTED,
                AccessLevel.ADMIN_ONLY,
            )
        }
        restricted = self.create_user("reason-restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("reason-admin")
        self.grant(admin, "view_admin_only_content")
        manager = self.create_user("reason-manager")
        manager.groups.add(Group.objects.get(name="Správce"))
        expectations = (
            (AnonymousUser(), {AccessLevel.PUBLIC}),
            (
                self.create_user("reason-ordinary"),
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
            (manager, set(relationships)),
        )
        permissionless_reason = self.item_for(
            get_relationship_overview(person=person),
            other,
        ).reasons[0]
        original_ids = permissionless_reason.relationship_ids

        for actor, levels in expectations:
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                reason = self.item_for(
                    self.visible(person, actor),
                    other,
                ).reasons[0]
                self.assertEqual(
                    reason.relationship_ids,
                    tuple(
                        sorted(relationships[level].pk for level in levels)
                    ),
                )
        self.assertEqual(permissionless_reason.relationship_ids, original_ids)

    def test_reason_and_item_are_removed_when_no_visible_id_remains(self) -> None:
        person = self.create_person("Vstup")
        hidden_only = self.create_person("Jen skrytý důvod")
        mixed = self.create_person("Více důvodů")
        self.create_relationship(
            "partner",
            person,
            hidden_only,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "partner",
            person,
            mixed,
            access_level=AccessLevel.RESTRICTED,
        )
        public_reason = self.create_relationship(
            "godparent",
            person,
            mixed,
        )

        result = self.visible(person, AnonymousUser())

        self.assertIsNone(self.item_for(result, hidden_only))
        mixed_item = self.item_for(result, mixed)
        self.assertEqual(len(mixed_item.reasons), 1)
        self.assertEqual(
            mixed_item.reasons[0].relationship_ids,
            (public_reason.pk,),
        )

    def test_biological_reason_requires_one_complete_visible_path(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        parent = self.create_person("Rodič")
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=parent,
            sibling_edge_access=AccessLevel.RESTRICTED,
        )
        restricted = self.create_user("biological-restricted")
        self.grant(restricted, "view_restricted_content")

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), sibling)
        )
        sibling_item = self.item_for(
            self.visible(person, restricted),
            sibling,
        )
        self.assertEqual(sibling_item.reasons[0].relationship_code, "biological")

    def test_hidden_parent_blocks_biological_reason(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        parent = self.create_person(
            "Skrytý rodič",
            access_level=AccessLevel.RESTRICTED,
        )
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=parent,
        )
        restricted = self.create_user("parent-restricted")
        self.grant(restricted, "view_restricted_content")

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), sibling)
        )
        self.assertIsNotNone(
            self.item_for(self.visible(person, restricted), sibling)
        )

    def test_second_complete_parent_path_is_sufficient(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        hidden_parent = self.create_person("Skrytý rodič")
        visible_parent = self.create_person("Viditelný rodič")
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=hidden_parent,
            sibling_edge_access=AccessLevel.RESTRICTED,
        )
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=visible_parent,
        )

        self.assertIsNotNone(
            self.item_for(self.visible(person, AnonymousUser()), sibling)
        )

    def test_visible_edges_from_different_parents_cannot_be_combined(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        first_parent = self.create_person("První rodič")
        second_parent = self.create_person("Druhý rodič")
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=first_parent,
            sibling_edge_access=AccessLevel.RESTRICTED,
        )
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=second_parent,
            input_edge_access=AccessLevel.RESTRICTED,
        )

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), sibling)
        )

    def test_parent_lifecycle_and_edge_lifecycle_are_enforced(self) -> None:
        person = self.create_person("Vstup")
        archived_sibling = self.create_person("Sourozenec archivovaného")
        archived_parent = self.create_person("Archivovaný rodič", archived=True)
        self.make_biological_path(
            person=person,
            sibling=archived_sibling,
            parent=archived_parent,
            archived_edges=True,
        )
        deleted_sibling = self.create_person("Sourozenec odstraněného")
        deleted_parent = self.create_person("Odstraněný rodič", deleted=True)
        self.make_biological_path(
            person=person,
            sibling=deleted_sibling,
            parent=deleted_parent,
        )
        actor = self.create_user("parent-lifecycle")
        self.grant(actor, "view_archived_person", "view_deleted_person")
        superuser = self.create_user("parent-super", is_superuser=True)

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), archived_sibling)
        )
        self.assertIsNotNone(
            self.item_for(self.visible(person, actor), archived_sibling)
        )
        for current_actor in (actor, superuser):
            self.assertIsNone(
                self.item_for(
                    self.visible(person, current_actor),
                    deleted_sibling,
                )
            )

    def test_deleted_parent_edge_cannot_authorize_biological_reason(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        parent = self.create_person("Rodič")
        _, sibling_edge = self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=parent,
        )
        Relationship.objects.filter(pk=sibling_edge.pk).update(
            deleted_at=timezone.now(),
        )

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), sibling)
        )

    def test_multiple_reasons_keep_permissionless_order(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Sourozenec")
        parent = self.create_person("Rodič")
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=parent,
        )
        self.create_relationship("sibling", person, sibling)
        self.create_relationship(
            "adoptive_sibling",
            person,
            sibling,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "social_sibling",
            person,
            sibling,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        permissionless = self.item_for(
            get_relationship_overview(person=person),
            sibling,
        )
        original_reasons = permissionless.reasons

        visible = self.item_for(
            self.visible(person, AnonymousUser()),
            sibling,
        )

        self.assertEqual(
            tuple(reason.relationship_code for reason in visible.reasons),
            ("biological", "sibling"),
        )
        self.assertEqual(permissionless.reasons, original_reasons)

    def test_inactive_and_staff_actor_gain_no_elevated_visibility(self) -> None:
        person = self.create_person("Vstup")
        public = self.create_person("Veřejná")
        restricted = self.create_person(
            "Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        archived = self.create_person("Archivovaná", archived=True)
        for other in (public, restricted, archived):
            self.create_relationship("partner", person, other)
        inactive = self.create_user(
            "inactive-manager",
            is_active=False,
            is_superuser=True,
        )
        inactive.groups.add(Group.objects.get(name="Správce"))
        staff = self.create_user("plain-staff", is_staff=True)

        for actor in (inactive, staff):
            with self.subTest(actor=actor.username):
                self.assertEqual(
                    {item.person.pk for item in self.visible(person, actor)},
                    {public.pk},
                )

    def test_user_defined_relationship_type_uses_access_policy(self) -> None:
        custom_type = RelationshipType.objects.create(
            code="custom_visible_test",
            name="Vlastní vazba",
            forward_label_male="známý",
            forward_label_female="známá",
            forward_label_unknown="známá osoba",
            reverse_label_male="známý",
            reverse_label_female="známá",
            reverse_label_unknown="známá osoba",
        )
        self.relationship_types[custom_type.code] = custom_type
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        self.create_relationship(
            custom_type.code,
            person,
            other,
            access_level=AccessLevel.RESTRICTED,
        )
        actor = self.create_user("custom-restricted")
        self.grant(actor, "view_restricted_content")

        self.assertIsNone(
            self.item_for(self.visible(person, AnonymousUser()), other)
        )
        self.assertIsNotNone(self.item_for(self.visible(person, actor), other))

    def test_selector_performs_no_writes_and_keeps_permissionless_objects(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        self.create_relationship("partner", person, other)
        permissionless = get_relationship_overview(person=person)
        item_state = permissionless[0]
        reason_state = permissionless[0].reasons[0]
        person_state = person.__dict__.copy()
        person_count = Person.objects.count()
        relationship_count = Relationship.objects.count()

        self.visible(person, AnonymousUser())

        self.assertEqual(Person.objects.count(), person_count)
        self.assertEqual(Relationship.objects.count(), relationship_count)
        self.assertEqual(person.__dict__, person_state)
        self.assertEqual(permissionless[0], item_state)
        self.assertEqual(permissionless[0].reasons[0], reason_state)

    def test_query_count_is_constant_without_n_plus_one(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("První sourozenec")
        parent = self.create_person("První rodič")
        self.make_biological_path(
            person=person,
            sibling=sibling,
            parent=parent,
        )
        self.create_relationship("godparent", person, sibling)
        actor = self.create_user("query-actor")

        with CaptureQueriesContext(connection) as small_context:
            self.visible(person, actor)

        for index in range(8):
            extra_sibling = self.create_person(f"Sourozenec {index}")
            extra_parent = self.create_person(f"Rodič {index}")
            self.make_biological_path(
                person=person,
                sibling=extra_sibling,
                parent=extra_parent,
            )
            self.create_relationship("godparent", person, extra_sibling)
            self.create_relationship("partner", person, extra_sibling)

        with CaptureQueriesContext(connection) as large_context:
            result = self.visible(person, actor)

        self.assertEqual(len(small_context), 19)
        self.assertEqual(len(small_context), len(large_context))
        self.assertEqual(len(result), 18)
