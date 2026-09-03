from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from people.models import Person, Relationship, RelationshipType

from .choices import SourceSupport
from .models import RelationshipSource, Source, SourceRole, SourceType
from .selectors import (
    get_relationship_source_links,
    get_visible_relationship_source_links,
)


class RelationshipSourceSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        for selector, names in (
            (get_relationship_source_links, ("relationship",)),
            (
                get_visible_relationship_source_links,
                ("relationship", "actor"),
            ),
        ):
            parameters = signature(selector).parameters
            self.assertEqual(tuple(parameters), names)
            self.assertTrue(
                all(
                    value.kind is Parameter.KEYWORD_ONLY
                    for value in parameters.values()
                )
            )


class RelationshipSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(username="author")
        self.person_a = Person.objects.create(first_name="Anna")
        self.person_b = Person.objects.create(first_name="Berta")
        self.relationship_type = RelationshipType.objects.create(
            code="test_source_relationship",
            name="Testovací vazba",
            forward_label_male="vazba",
            forward_label_female="vazba",
            forward_label_unknown="vazba",
            reverse_label_male="vazba",
            reverse_label_female="vazba",
            reverse_label_unknown="vazba",
            is_symmetric=True,
        )
        self.relationship = self.make_relationship(
            self.person_a,
            self.person_b,
        )
        self.source_type = SourceType.objects.create(code="archive", name="Archiv")
        self.role = SourceRole.objects.create(
            code="evidence",
            name="Doklad",
            sort_order=10,
        )

    def make_relationship(self, person_a, person_b, **overrides) -> Relationship:
        values = {
            "relationship_type": self.relationship_type,
            "person_a": person_a,
            "person_b": person_b,
            "created_by": self.author,
        }
        values.update(overrides)
        return Relationship.objects.create(**values)

    def source(self, title: str, **overrides) -> Source:
        values = {
            "source_type": self.source_type,
            "title": title,
            "created_by": self.author,
        }
        values.update(overrides)
        return Source.objects.create(**values)

    def link(self, title: str, **overrides) -> RelationshipSource:
        values = {
            "relationship": self.relationship,
            "source": self.source(title),
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "created_by": self.author,
        }
        values.update(overrides)
        return RelationshipSource.objects.create(**values)

    @staticmethod
    def user(username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def visible(self, actor, *, relationship=None) -> QuerySet:
        return get_visible_relationship_source_links(
            relationship=relationship or self.relationship,
            actor=actor,
        )

    def test_permissionless_history_excludes_only_deleted_link(self) -> None:
        active = self.link("Aktivní")
        archived = self.link("Archivovaná", archived_at=timezone.now())
        hidden = self.link("Skrytá", access_level=AccessLevel.ADMIN_ONLY)
        self.link("Odstraněná", deleted_at=timezone.now())

        queryset = get_relationship_source_links(
            relationship=self.relationship
        )
        self.assertIsInstance(queryset, QuerySet)
        self.assertEqual(list(queryset), [active, archived, hidden])

    def test_invalid_relationship_has_stable_error_in_both_selectors(self) -> None:
        missing = self.make_relationship(
            Person.objects.create(first_name="Cyril"),
            Person.objects.create(first_name="Dana"),
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        for relationship in (Relationship(), missing, object()):
            for selector, arguments in (
                (get_relationship_source_links, {"relationship": relationship}),
                (
                    get_visible_relationship_source_links,
                    {"relationship": relationship, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["relationship"][0].code,
                        "relationship_unsaved",
                    )

    def test_target_requires_visible_relationship_and_both_people(self) -> None:
        manager = self.user("manager")
        manager.user_permissions.add(
            self.permission("view_restricted_content"),
            self.permission("view_archived_person"),
        )
        self.link("Zdroj")
        Relationship.objects.filter(pk=self.relationship.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(len(self.visible(AnonymousUser())), 1)
        Relationship.objects.filter(pk=self.relationship.pk).update(
            archived_at=None,
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)

        Person.objects.filter(pk=self.person_b.pk).update(
            archived_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)
        Person.objects.filter(pk=self.person_b.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(manager)
        with self.assertRaises(PermissionDenied):
            self.visible(
                self.user("superuser", is_superuser=True),
                relationship=self.relationship,
            )

        Person.objects.filter(pk=self.person_b.pk).update(deleted_at=None)
        Relationship.objects.filter(pk=self.relationship.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(manager)

    def test_result_requires_visible_active_link_and_source(self) -> None:
        public = self.link("Veřejný")
        restricted_link = self.link(
            "Omezená vazba",
            access_level=AccessLevel.RESTRICTED,
        )
        restricted_source = self.link(
            "Omezený zdroj",
            source=self.source(
                "Omezený",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        self.link("Archivovaná vazba", archived_at=timezone.now())
        self.link(
            "Archivovaný zdroj",
            source=self.source("Archiv", archived_at=timezone.now()),
        )
        manager = self.user("access-manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))

        self.assertEqual(list(self.visible(AnonymousUser())), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted_link, restricted_source],
        )

    def test_shared_source_does_not_reveal_hidden_relationship(self) -> None:
        shared = self.source("Sdílený")
        public_link = RelationshipSource.objects.create(
            relationship=self.relationship,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )
        hidden_relationship = self.make_relationship(
            Person.objects.create(first_name="Eva"),
            Person.objects.create(
                first_name="František",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )
        RelationshipSource.objects.create(
            relationship=hidden_relationship,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )

        self.assertEqual(list(self.visible(AnonymousUser())), [public_link])
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), relationship=hidden_relationship)

    def test_order_preload_and_lazy_filters_cover_complete_path(self) -> None:
        later_role = SourceRole.objects.create(
            code="later",
            name="Pozdější",
            sort_order=20,
        )
        later = self.link("Pozdější", role=later_role)
        earlier = self.link("Dřívější")
        with CaptureQueriesContext(connection) as captured:
            result = list(self.visible(AnonymousUser()))
            for link in result:
                str(link.relationship.relationship_type)
                str(link.relationship.person_a)
                str(link.relationship.person_b)
                link.relationship.created_by.username
                str(link.source.source_type)
                link.source.created_by.username
                str(link.role)
                link.created_by.username
        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(captured), 3)

        now = timezone.now()
        cases = (
            (Person, self.person_a.pk, {"archived_at": now}, None),
            (Person, self.person_b.pk, {"deleted_at": now}, None),
            (Relationship, self.relationship.pk, {"deleted_at": now}, None),
            (
                RelationshipSource,
                earlier.pk,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
            ),
            (Source, earlier.source_id, {"deleted_at": now}, [later]),
        )
        for model, object_id, change, expected in cases:
            with self.subTest(model=model.__name__):
                queryset = self.visible(AnonymousUser())
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), expected or [])
                reset = {
                    field: None if field.endswith("_at") else AccessLevel.PUBLIC
                    for field in change
                }
                model.objects.filter(pk=object_id).update(**reset)
