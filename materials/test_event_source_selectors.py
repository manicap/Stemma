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
from events.models import Event, EventType
from places.models import Place

from .choices import SourceSupport
from .models import EventSource, Source, SourceRole, SourceType
from .selectors import get_event_source_links, get_visible_event_source_links


class EventSourceSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        expectations = (
            (get_event_source_links, ("event",)),
            (get_visible_event_source_links, ("event", "actor")),
        )
        for selector, names in expectations:
            parameters = signature(selector).parameters
            self.assertEqual(tuple(parameters), names)
            self.assertTrue(
                all(
                    value.kind is Parameter.KEYWORD_ONLY
                    for value in parameters.values()
                )
            )


class EventSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(username="author")
        self.place = Place.objects.create(name="Praha", normalized_name="praha")
        self.event_type = EventType.objects.create(code="source", name="Událost")
        self.event = Event.objects.create(
            event_type=self.event_type,
            place=self.place,
            created_by=self.author,
        )
        self.source_type = SourceType.objects.create(code="archive", name="Archiv")
        self.role = SourceRole.objects.create(
            code="evidence",
            name="Doklad",
            sort_order=10,
        )

    def source(self, title: str, **overrides) -> Source:
        values = {
            "source_type": self.source_type,
            "title": title,
            "created_by": self.author,
        }
        values.update(overrides)
        return Source.objects.create(**values)

    def link(self, title: str, **overrides) -> EventSource:
        values = {
            "event": self.event,
            "source": self.source(title),
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "created_by": self.author,
        }
        values.update(overrides)
        return EventSource.objects.create(**values)

    @staticmethod
    def user(username: str):
        return get_user_model().objects.create_user(username=username)

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def visible(self, actor, *, event=None) -> QuerySet:
        return get_visible_event_source_links(
            event=event or self.event,
            actor=actor,
        )

    def test_permissionless_history_excludes_only_deleted_link(self) -> None:
        active = self.link("Aktivní")
        archived = self.link("Archivovaná", archived_at=timezone.now())
        hidden = self.link("Skrytá", access_level=AccessLevel.ADMIN_ONLY)
        self.link("Odstraněná", deleted_at=timezone.now())

        queryset = get_event_source_links(event=self.event)
        self.assertIsInstance(queryset, QuerySet)
        self.assertEqual(
            list(queryset),
            [active, archived, hidden],
        )

    def test_invalid_event_has_stable_error_in_both_selectors(self) -> None:
        missing = Event.objects.create(event_type=self.event_type)
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        for event in (Event(), missing, object()):
            for selector, arguments in (
                (get_event_source_links, {"event": event}),
                (
                    get_visible_event_source_links,
                    {"event": event, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(event=event, selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["event"][0].code,
                        "event_unsaved",
                    )

    def test_event_access_and_lifecycle_are_mandatory(self) -> None:
        reader = self.user("reader")
        manager = self.user("manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))
        restricted = Event.objects.create(
            event_type=self.event_type,
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(reader, event=restricted)
        self.assertIsInstance(self.visible(manager, event=restricted), QuerySet)

        for field in ("archived_at", "deleted_at"):
            Event.objects.filter(pk=self.event.pk).update(
                **{field: timezone.now()}
            )
            with self.assertRaises(PermissionDenied):
                self.visible(manager)
            Event.objects.filter(pk=self.event.pk).update(**{field: None})

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
        self.link(
            "Odstraněný zdroj",
            source=self.source("Odstraněný", deleted_at=timezone.now()),
        )
        manager = self.user("access-manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))

        self.assertEqual(list(self.visible(AnonymousUser())), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted_link, restricted_source],
        )

    def test_visible_shared_source_does_not_reveal_hidden_event(self) -> None:
        shared = self.source("Sdílený")
        public_event = Event.objects.create(event_type=self.event_type)
        public_link = EventSource.objects.create(
            event=public_event,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )
        hidden_event = Event.objects.create(
            event_type=self.event_type,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        EventSource.objects.create(
            event=hidden_event,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )

        self.assertEqual(
            list(self.visible(AnonymousUser(), event=public_event)),
            [public_link],
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), event=hidden_event)

    def test_order_query_profile_and_lazy_fresh_state(self) -> None:
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
                str(link.event.event_type)
                link.event.place
                link.event.created_by.username
                str(link.source.source_type)
                link.source.created_by.username
                str(link.role)
                link.created_by.username
        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(captured), 3)

        now = timezone.now()
        cases = (
            (
                Event,
                self.event.pk,
                {"archived_at": now},
                {"archived_at": None},
                [],
            ),
            (
                EventSource,
                earlier.pk,
                {"access_level": AccessLevel.RESTRICTED},
                {"access_level": AccessLevel.PUBLIC},
                [later],
            ),
            (
                Source,
                earlier.source_id,
                {"deleted_at": now},
                {"deleted_at": None},
                [later],
            ),
        )
        for model, object_id, change, reset, expected in cases:
            with self.subTest(model=model.__name__):
                queryset = self.visible(AnonymousUser())
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), expected)
                model.objects.filter(pk=object_id).update(**reset)
