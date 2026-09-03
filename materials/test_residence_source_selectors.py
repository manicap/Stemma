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
from people.models import Person
from places.models import Place, Residence, ResidenceType

from .choices import SourceSupport
from .models import ResidenceSource, Source, SourceRole, SourceType
from .selectors import (
    get_residence_source_links,
    get_visible_residence_source_links,
)


class ResidenceSourceSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        for selector, names in (
            (get_residence_source_links, ("residence",)),
            (
                get_visible_residence_source_links,
                ("residence", "actor"),
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


class ResidenceSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(username="author")
        self.person = Person.objects.create(first_name="Anna")
        self.residence_type = ResidenceType.objects.create(
            code="test_source_residence",
            name="Bydliště",
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.residence = self.make_residence()
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archiv",
        )
        self.role = SourceRole.objects.create(
            code="evidence",
            name="Doklad",
            sort_order=10,
        )

    def make_residence(self, **overrides) -> Residence:
        values = {
            "person": self.person,
            "residence_type": self.residence_type,
            "place": self.place,
            "created_by": self.author,
        }
        values.update(overrides)
        residence = Residence(**values)
        residence.full_clean()
        residence.save()
        return residence

    def source(self, title: str, **overrides) -> Source:
        values = {
            "source_type": self.source_type,
            "title": title,
            "created_by": self.author,
        }
        values.update(overrides)
        return Source.objects.create(**values)

    def link(self, title: str, **overrides) -> ResidenceSource:
        values = {
            "residence": self.residence,
            "source": self.source(title),
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "created_by": self.author,
        }
        values.update(overrides)
        return ResidenceSource.objects.create(**values)

    @staticmethod
    def user(username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def visible(self, actor, *, residence=None) -> QuerySet:
        return get_visible_residence_source_links(
            residence=residence or self.residence,
            actor=actor,
        )

    def test_permissionless_history_excludes_only_deleted_link(self) -> None:
        active = self.link("Aktivní")
        archived = self.link("Archivovaná", archived_at=timezone.now())
        hidden = self.link("Skrytá", access_level=AccessLevel.ADMIN_ONLY)
        deleted_source = self.link(
            "Odstraněný zdroj",
            source=self.source("Odstraněný", deleted_at=timezone.now()),
        )
        self.link("Odstraněná vazba", deleted_at=timezone.now())

        self.assertEqual(
            list(get_residence_source_links(residence=self.residence)),
            [active, archived, hidden, deleted_source],
        )

    def test_invalid_residence_has_stable_error_in_both_selectors(self) -> None:
        missing = self.make_residence(address_text="Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        for residence in (Residence(), missing, object()):
            for selector, arguments in (
                (get_residence_source_links, {"residence": residence}),
                (
                    get_visible_residence_source_links,
                    {"residence": residence, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["residence"][0].code,
                        "residence_unsaved",
                    )

    def test_target_enforces_residence_and_parent_person_policy(self) -> None:
        manager = self.user("manager")
        manager.user_permissions.add(
            self.permission("view_restricted_content"),
            self.permission("view_archived_person"),
            self.permission("view_deleted_person"),
        )
        self.link("Zdroj")
        Residence.objects.filter(pk=self.residence.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(len(self.visible(AnonymousUser())), 1)
        Residence.objects.filter(pk=self.residence.pk).update(
            archived_at=None,
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)

        Residence.objects.filter(pk=self.residence.pk).update(
            access_level=AccessLevel.PUBLIC
        )
        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.RESTRICTED
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)
        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)
        Person.objects.filter(pk=self.person.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)

        Residence.objects.filter(pk=self.residence.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(self.user("superuser", is_superuser=True))

    def test_place_and_inactive_lookups_are_not_authorization_layers(self) -> None:
        link = self.link("Historický kontext")
        Place.objects.filter(pk=self.place.pk).update(
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        ResidenceType.objects.filter(pk=self.residence_type.pk).update(
            is_active=False
        )
        SourceType.objects.filter(pk=self.source_type.pk).update(is_active=False)
        SourceRole.objects.filter(pk=self.role.pk).update(is_active=False)

        self.assertEqual(list(self.visible(AnonymousUser())), [link])

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

    def test_actor_state_is_loaded_fresh_for_each_call(self) -> None:
        link = self.link("Omezený", access_level=AccessLevel.RESTRICTED)
        actor = self.user("stale-actor")
        actor.user_permissions.add(self.permission("view_restricted_content"))
        self.assertEqual(list(self.visible(actor)), [link])
        actor.user_permissions.remove(self.permission("view_restricted_content"))
        self.assertEqual(list(self.visible(actor)), [])
        get_user_model().objects.filter(pk=actor.pk).update(is_superuser=True)
        self.assertEqual(list(self.visible(actor)), [link])
        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=False,
            is_active=False,
        )
        self.assertEqual(list(self.visible(actor)), [])

    def test_invalid_actor_uses_central_stable_error(self) -> None:
        for actor, code in (
            (None, "actor_invalid"),
            (object(), "actor_invalid"),
            (get_user_model()(username="unsaved"), "actor_unsaved"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as context:
                    self.visible(actor)
                self.assertEqual(
                    context.exception.error_dict["actor"][0].code,
                    code,
                )

    def test_shared_source_does_not_reveal_hidden_residence(self) -> None:
        shared = self.source("Sdílený")
        public_link = ResidenceSource.objects.create(
            residence=self.residence,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )
        hidden = self.make_residence(
            address_text="Skryté",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        ResidenceSource.objects.create(
            residence=hidden,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )

        self.assertEqual(list(self.visible(AnonymousUser())), [public_link])
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), residence=hidden)

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
                str(link.residence.person)
                str(link.residence.residence_type)
                str(link.residence.place)
                link.residence.created_by.username
                str(link.source.source_type)
                link.source.created_by.username
                str(link.role)
                link.created_by.username
        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(captured), 3)

        now = timezone.now()
        cases = (
            (
                Person,
                self.person.pk,
                {"archived_at": now},
                None,
                {"archived_at": None},
            ),
            (
                Person,
                self.person.pk,
                {"deleted_at": now},
                None,
                {"deleted_at": None},
            ),
            (
                Person,
                self.person.pk,
                {"access_level": AccessLevel.RESTRICTED},
                None,
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Residence,
                self.residence.pk,
                {"access_level": AccessLevel.RESTRICTED},
                None,
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Residence,
                self.residence.pk,
                {"archived_at": now},
                [earlier, later],
                {"archived_at": None},
            ),
            (
                Residence,
                self.residence.pk,
                {"deleted_at": now},
                None,
                {"deleted_at": None},
            ),
            (
                ResidenceSource,
                earlier.pk,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                ResidenceSource,
                earlier.pk,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                ResidenceSource,
                earlier.pk,
                {"deleted_at": now},
                [later],
                {"deleted_at": None},
            ),
            (
                Source,
                earlier.source_id,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                Source,
                earlier.source_id,
                {"deleted_at": now},
                [later],
                {"deleted_at": None},
            ),
            (
                Source,
                earlier.source_id,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
        )
        for model, object_id, change, expected, reset in cases:
            with self.subTest(model=model.__name__):
                queryset = self.visible(AnonymousUser())
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), expected or [])
                model.objects.filter(pk=object_id).update(**reset)
