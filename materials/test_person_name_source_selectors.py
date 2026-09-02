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
from people.models import NameType, Person, PersonName

from .choices import SourceSupport
from .models import PersonNameSource, Source, SourceRole, SourceType
from .selectors import (
    get_person_name_source_links,
    get_visible_person_name_source_links,
)


class PersonNameSourceSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        expectations = (
            (get_person_name_source_links, ("person_name",)),
            (
                get_visible_person_name_source_links,
                ("person_name", "actor"),
            ),
        )
        for selector, names in expectations:
            with self.subTest(selector=selector.__name__):
                parameters = signature(selector).parameters
                self.assertEqual(tuple(parameters), names)
                self.assertTrue(
                    all(
                        value.kind is Parameter.KEYWORD_ONLY
                        for value in parameters.values()
                    )
                )


class PersonNameSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Anna")
        self.name_type = NameType.objects.create(code="alias", name="Alias")
        self.person_name = self.make_name("Nováková")
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archiv",
        )
        self.role = SourceRole.objects.create(code="evidence", name="Doklad")

    def make_name(self, value: str, **overrides) -> PersonName:
        values = {
            "person": self.person,
            "name_type": self.name_type,
            "value": value,
            "normalized_value": value.lower(),
        }
        values.update(overrides)
        return PersonName.objects.create(**values)

    def make_source(self, title: str, **overrides) -> Source:
        values = {"source_type": self.source_type, "title": title}
        values.update(overrides)
        return Source.objects.create(**values)

    def make_link(self, title: str, **overrides) -> PersonNameSource:
        values = {
            "person_name": self.person_name,
            "source": self.make_source(title),
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
        }
        values.update(overrides)
        return PersonNameSource.objects.create(**values)

    @staticmethod
    def user(username: str):
        return get_user_model().objects.create_user(username=username)

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def test_permissionless_history_only_excludes_deleted_link(self) -> None:
        active = self.make_link("Aktivní")
        archived = self.make_link("Archivovaná", archived_at=timezone.now())
        hidden = self.make_link(
            "Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.make_link("Odstraněná", deleted_at=timezone.now())

        self.assertEqual(
            list(get_person_name_source_links(person_name=self.person_name)),
            [active, archived, hidden],
        )

    def test_invalid_name_uses_stable_error(self) -> None:
        missing = self.make_name("Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        selectors = (
            get_person_name_source_links,
            get_visible_person_name_source_links,
        )
        for selector in selectors:
            for value in (PersonName(value="Neuložené"), missing, object()):
                with self.subTest(selector=selector.__name__, value=value):
                    arguments = {"person_name": value}
                    if selector is get_visible_person_name_source_links:
                        arguments["actor"] = AnonymousUser()
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["person_name"][0].code,
                        "person_name_unsaved",
                    )

    def test_target_requires_visible_person_and_name(self) -> None:
        ordinary = self.user("ordinary")
        restricted_reader = self.user("restricted")
        restricted_reader.user_permissions.add(
            self.permission("view_restricted_content")
        )
        self.make_link("Zdroj")

        PersonName.objects.filter(pk=self.person_name.pk).update(
            access_level=AccessLevel.RESTRICTED
        )
        with self.assertRaises(PermissionDenied):
            get_visible_person_name_source_links(
                person_name=self.person_name,
                actor=ordinary,
            )
        self.assertEqual(
            len(
                get_visible_person_name_source_links(
                    person_name=self.person_name,
                    actor=restricted_reader,
                )
            ),
            1,
        )

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(PermissionDenied):
            get_visible_person_name_source_links(
                person_name=self.person_name,
                actor=restricted_reader,
            )

    def test_result_requires_visible_active_link_and_source(self) -> None:
        public = self.make_link("Veřejný")
        restricted_link = self.make_link(
            "Omezená vazba",
            access_level=AccessLevel.RESTRICTED,
        )
        restricted_source = self.make_link(
            "Omezený zdroj",
            source=self.make_source(
                "Omezený",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        self.make_link("Archivovaná vazba", archived_at=timezone.now())
        self.make_link(
            "Archivovaný zdroj",
            source=self.make_source("Archiv", archived_at=timezone.now()),
        )
        self.make_link(
            "Odstraněný zdroj",
            source=self.make_source("Odstraněný", deleted_at=timezone.now()),
        )
        manager = self.user("manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))

        self.assertEqual(
            list(
                get_visible_person_name_source_links(
                    person_name=self.person_name,
                    actor=AnonymousUser(),
                )
            ),
            [public],
        )
        self.assertEqual(
            list(
                get_visible_person_name_source_links(
                    person_name=self.person_name,
                    actor=manager,
                )
            ),
            [public, restricted_link, restricted_source],
        )

    def test_other_visible_link_never_reveals_hidden_target(self) -> None:
        shared_source = self.make_source("Sdílený zdroj")
        public_name = self.make_name("Veřejné jméno")
        public_link = PersonNameSource.objects.create(
            person_name=public_name,
            source=shared_source,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )
        hidden_name = self.make_name(
            "Skryté jméno",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        PersonNameSource.objects.create(
            person_name=hidden_name,
            source=shared_source,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )

        self.assertEqual(
            list(
                get_visible_person_name_source_links(
                    person_name=public_name,
                    actor=AnonymousUser(),
                )
            ),
            [public_link],
        )
        with self.assertRaises(PermissionDenied):
            get_visible_person_name_source_links(
                person_name=hidden_name,
                actor=AnonymousUser(),
            )

    def test_model_ordering_uses_role_order_before_primary_key(self) -> None:
        later_role = SourceRole.objects.create(
            code="later",
            name="Pozdější",
            sort_order=20,
        )
        earlier_role = SourceRole.objects.create(
            code="earlier",
            name="Dřívější",
            sort_order=10,
        )
        later = self.make_link("Pozdější", role=later_role)
        earlier = self.make_link("Dřívější", role=earlier_role)

        self.assertEqual(
            list(get_person_name_source_links(person_name=self.person_name)),
            [earlier, later],
        )

    def test_all_layers_are_rechecked_when_lazy_queryset_is_evaluated(self) -> None:
        link = self.make_link("Zdroj")
        now = timezone.now()
        cases = (
            (Person, self.person.pk, {"archived_at": now}, {"archived_at": None}),
            (
                PersonName,
                self.person_name.pk,
                {"access_level": AccessLevel.ADMIN_ONLY},
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                PersonNameSource,
                link.pk,
                {"archived_at": now},
                {"archived_at": None},
            ),
            (Source, link.source_id, {"deleted_at": now}, {"deleted_at": None}),
        )
        for model, object_id, change, reset in cases:
            with self.subTest(model=model.__name__):
                queryset = get_visible_person_name_source_links(
                    person_name=self.person_name,
                    actor=AnonymousUser(),
                )
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), [])
                model.objects.filter(pk=object_id).update(**reset)

    def test_parent_person_lifecycle_uses_explicit_permissions(self) -> None:
        link = self.make_link("Zdroj")
        ordinary = self.user("lifecycle-ordinary")
        manager = self.user("lifecycle-manager")
        manager.user_permissions.add(
            self.permission("view_archived_person"),
            self.permission("view_deleted_person"),
        )
        for field in ("archived_at", "deleted_at"):
            with self.subTest(field=field):
                Person.objects.filter(pk=self.person.pk).update(
                    **{field: timezone.now()}
                )
                with self.assertRaises(PermissionDenied):
                    get_visible_person_name_source_links(
                        person_name=self.person_name,
                        actor=ordinary,
                    )
                self.assertEqual(
                    list(
                        get_visible_person_name_source_links(
                            person_name=self.person_name,
                            actor=manager,
                        )
                    ),
                    [link],
                )
                Person.objects.filter(pk=self.person.pk).update(**{field: None})

    def test_archived_or_deleted_name_is_always_denied(self) -> None:
        self.make_link("Zdroj")
        for field in ("archived_at", "deleted_at"):
            with self.subTest(field=field):
                PersonName.objects.filter(pk=self.person_name.pk).update(
                    **{field: timezone.now()}
                )
                with self.assertRaises(PermissionDenied):
                    get_visible_person_name_source_links(
                        person_name=self.person_name,
                        actor=AnonymousUser(),
                    )
                PersonName.objects.filter(pk=self.person_name.pk).update(
                    **{field: None}
                )

    def test_query_profile_preloads_complete_context(self) -> None:
        author = self.user("author")
        link = self.make_link("Zdroj")
        PersonName.objects.filter(pk=self.person_name.pk).update(
            created_by=author
        )
        Source.objects.filter(pk=link.source_id).update(created_by=author)
        PersonNameSource.objects.filter(pk=link.pk).update(created_by=author)
        with CaptureQueriesContext(connection) as captured:
            links = list(
                get_visible_person_name_source_links(
                    person_name=self.person_name,
                    actor=AnonymousUser(),
                )
            )
            for link in links:
                str(link.person_name.person)
                str(link.person_name.name_type)
                str(link.source.source_type)
                str(link.role)
                link.person_name.created_by.username
                link.source.created_by.username
                link.created_by.username

        self.assertEqual(len(captured), 3)
        self.assertIsInstance(
            get_person_name_source_links(person_name=self.person_name),
            QuerySet,
        )
