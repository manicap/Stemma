from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision
from people.models import Person
from places.models import Place

from .models import Event, EventParticipant, EventType, ParticipantRole
from .selectors import get_visible_person_events


class VisiblePersonEventSelectorTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.event_type = EventType.objects.get(code="other")
        cls.role = ParticipantRole.objects.get(code="other")

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
        )

    @staticmethod
    def grant(actor, codename: str) -> None:
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                content_type__model="user",
                codename=codename,
            )
        )

    def user(self, username: str, *permissions: str, **values: object):
        actor = get_user_model().objects.create_user(
            username=username,
            password="test-password",
            **values,
        )
        for codename in permissions:
            self.grant(actor, codename)
        return actor

    def create_event(self, **values: object) -> Event:
        event = Event.objects.create(event_type=self.event_type, **values)
        EventParticipant.objects.create(
            event=event,
            person=self.person,
            role=self.role,
        )
        return event

    def visible(self, actor=None):
        return get_visible_person_events(
            person=self.person,
            actor=actor or AnonymousUser(),
        )

    def test_returns_visible_active_events_in_model_order(self) -> None:
        later = self.create_event(
            title="Pozdější",
            date_precision=DatePrecision.YEAR,
            start_year=1950,
        )
        earlier = self.create_event(
            title="Dřívější",
            date_precision=DatePrecision.YEAR,
            start_year=1900,
        )

        self.assertEqual(list(self.visible()), [earlier, later])

    def test_access_levels_use_central_actor_policy(self) -> None:
        restricted = self.create_event(
            title="Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        admin_only = self.create_event(
            title="Správcovská",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        restricted_actor = self.user(
            "restricted-selector",
            "view_restricted_content",
        )
        admin_actor = self.user(
            "admin-selector",
            "view_admin_only_content",
        )
        superuser = self.user("super-selector", is_superuser=True)

        self.assertNotIn(restricted, self.visible())
        self.assertEqual(list(self.visible(restricted_actor)), [restricted])
        self.assertEqual(list(self.visible(admin_actor)), [admin_only])
        self.assertCountEqual(
            self.visible(superuser),
            (restricted, admin_only),
        )

    def test_inactive_and_staff_do_not_gain_content_access(self) -> None:
        self.create_event(
            title="Neveřejná",
            access_level=AccessLevel.RESTRICTED,
        )
        inactive = self.user(
            "inactive-selector",
            "view_restricted_content",
            is_active=False,
        )
        staff = self.user("staff-selector", is_staff=True)

        self.assertFalse(self.visible(inactive).exists())
        self.assertFalse(self.visible(staff).exists())

    def test_archived_and_soft_deleted_events_are_excluded(self) -> None:
        archived = self.create_event(title="Archivovaná")
        deleted = self.create_event(title="Odstraněná")
        Event.objects.filter(pk=archived.pk).update(
            archived_at=timezone.now()
        )
        Event.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())

        self.assertFalse(self.visible().exists())

    def test_input_person_is_checked_fail_closed(self) -> None:
        hidden = Person.objects.create(
            first_name="Skrytá",
            last_name="Osoba",
            access_level=AccessLevel.RESTRICTED,
        )
        missing = Person(pk=999_999)

        for person in (hidden, missing):
            with self.subTest(person=person.pk), self.assertRaises(
                PermissionDenied
            ):
                get_visible_person_events(
                    person=person,
                    actor=AnonymousUser(),
                )
        with self.assertRaisesMessage(ValidationError, "uložená"):
            get_visible_person_events(
                person=Person(),
                actor=AnonymousUser(),
            )

    def test_place_name_is_exposed_only_when_place_is_visible_and_active(self) -> None:
        visible_place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        hidden_place = Place.objects.create(
            name="Utajené místo",
            normalized_name="utajene misto",
            access_level=AccessLevel.RESTRICTED,
        )
        archived_place = Place.objects.create(
            name="Archivované místo",
            normalized_name="archivovane misto",
            archived_at=timezone.now(),
        )
        deleted_place = Place.objects.create(
            name="Odstraněné místo",
            normalized_name="odstranene misto",
            deleted_at=timezone.now(),
        )
        self.create_event(title="Viditelné místo", place=visible_place)
        self.create_event(title="Skryté místo", place=hidden_place)
        self.create_event(title="Archivovaný kontext", place=archived_place)
        self.create_event(title="Odstraněný kontext", place=deleted_place)

        events = {event.title: event for event in self.visible()}

        self.assertEqual(
            events["Viditelné místo"].presentation_place_name,
            "Praha",
        )
        self.assertIsNone(
            events["Skryté místo"].presentation_place_name
        )
        self.assertIsNone(
            events["Archivovaný kontext"].presentation_place_name
        )
        self.assertIsNone(
            events["Odstraněný kontext"].presentation_place_name
        )

    def test_query_count_is_constant_and_participants_are_not_prefetched(self) -> None:
        self.create_event(title="První")
        with CaptureQueriesContext(connection) as baseline_queries:
            baseline = list(self.visible())
        for index in range(5):
            self.create_event(title=f"Další {index}")
        with CaptureQueriesContext(connection) as expanded_queries:
            expanded = list(self.visible())

        self.assertEqual(len(expanded_queries), len(baseline_queries))
        self.assertEqual(len(baseline_queries), 2)
        self.assertEqual(len(baseline), 1)
        self.assertEqual(len(expanded), 6)
        self.assertFalse(
            hasattr(expanded[0], "_prefetched_objects_cache")
        )
