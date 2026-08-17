from dataclasses import FrozenInstanceError, is_dataclass
from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision
from people.models import Person
from places.models import Place, PlaceType

from .models import (
    AllowedEventRole,
    Event,
    EventParticipant,
    EventType,
    ParticipantRole,
)
from .services import (
    EventInput,
    EventParticipantInput,
    create_event,
    replace_event_participants,
    update_event,
)


class EventAggregateServiceApiTests(SimpleTestCase):
    def test_event_input_is_frozen_slotted_dataclass(self) -> None:
        event_type = EventType(code="service", name="Servisní")
        data = EventInput(event_type=event_type)

        self.assertTrue(is_dataclass(EventInput))
        self.assertTrue(EventInput.__dataclass_params__.frozen)
        self.assertFalse(hasattr(data, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            data.title = "Změna"

    def test_public_service_contracts_are_keyword_only(self) -> None:
        for service in (create_event, update_event):
            self.assertTrue(
                all(
                    parameter.kind is Parameter.KEYWORD_ONLY
                    for parameter in signature(service).parameters.values()
                )
            )


class EventAggregateServiceTests(TestCase):
    def setUp(self) -> None:
        self.event_type = EventType.objects.create(
            code="aggregate_service",
            name="Agregátová událost",
            default_access_level=AccessLevel.AUTHENTICATED,
            default_show_in_overview=True,
        )
        self.role = ParticipantRole.objects.create(
            code="aggregate_subject",
            name="Hlavní osoba agregátu",
        )
        AllowedEventRole.objects.create(
            event_type=self.event_type,
            participant_role=self.role,
            min_count=1,
            max_count=1,
        )
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
        )
        self.user = get_user_model().objects.create_user(
            username="event-author",
            password="local-test-only",
        )
        place_type = PlaceType.objects.create(
            code="aggregate_place",
            name="Místo agregátu",
        )
        self.place = Place.objects.create(
            name="Praha",
            place_type=place_type,
        )

    def participant(self) -> EventParticipantInput:
        return EventParticipantInput(person=self.person, role=self.role)

    def assert_error_code(
        self,
        context,
        *,
        key: str,
        code: str,
    ) -> None:
        self.assertIn(key, context.exception.error_dict)
        self.assertIn(
            code,
            [error.code for error in context.exception.error_dict[key]],
        )

    def test_create_snapshots_type_defaults_and_writes_participants(self) -> None:
        event = create_event(
            data=EventInput(
                event_type=self.event_type,
                place=self.place,
                title="  Rodinná událost  ",
            ),
            participants=(self.participant(),),
            created_by=self.user,
            require_complete=True,
        )

        self.assertEqual(event.title, "Rodinná událost")
        self.assertEqual(event.place, self.place)
        self.assertEqual(event.created_by, self.user)
        self.assertEqual(event.access_level, AccessLevel.AUTHENTICATED)
        self.assertTrue(event.show_in_overview)
        self.assertTrue(
            event.participants.filter(
                person=self.person,
                role=self.role,
            ).exists()
        )

    def test_create_accepts_explicit_default_overrides(self) -> None:
        event = create_event(
            data=EventInput(
                event_type=self.event_type,
                access_level=AccessLevel.RESTRICTED,
                show_in_overview=False,
            )
        )

        self.assertEqual(event.access_level, AccessLevel.RESTRICTED)
        self.assertFalse(event.show_in_overview)

    def test_create_rolls_back_event_when_participants_are_invalid(self) -> None:
        with self.assertRaises(ValidationError):
            create_event(
                data=EventInput(
                    event_type=self.event_type,
                    title="Nesmí zůstat",
                ),
                participants=(),
                require_complete=True,
            )

        self.assertFalse(Event.objects.filter(title="Nesmí zůstat").exists())

    def test_update_replaces_event_and_participants_atomically(self) -> None:
        event = create_event(
            data=EventInput(event_type=self.event_type, title="Původní"),
            participants=(self.participant(),),
        )

        updated = update_event(
            event=event,
            data=EventInput(
                event_type=self.event_type,
                title="  Nový název  ",
                date_precision=DatePrecision.YEAR,
                start_year=1910,
            ),
            participants=(self.participant(),),
            require_complete=True,
        )

        self.assertEqual(updated.title, "Nový název")
        self.assertEqual(updated.start_year, 1910)
        self.assertEqual(updated.access_level, AccessLevel.AUTHENTICATED)
        self.assertTrue(updated.show_in_overview)
        self.assertEqual(updated.participants.count(), 1)

    def test_update_rolls_back_event_fields_on_participant_error(self) -> None:
        event = create_event(
            data=EventInput(event_type=self.event_type, title="Původní"),
            participants=(self.participant(),),
        )

        with self.assertRaises(ValidationError):
            update_event(
                event=event,
                data=EventInput(event_type=self.event_type, title="Neplatný"),
                participants=(),
                require_complete=True,
            )

        event.refresh_from_db()
        self.assertEqual(event.title, "Původní")
        self.assertEqual(event.participants.count(), 1)

    def test_update_does_not_resnapshot_changed_type_defaults(self) -> None:
        event = create_event(
            data=EventInput(event_type=self.event_type),
        )
        other_type = EventType.objects.create(
            code="aggregate_other",
            name="Jiný typ",
            default_access_level=AccessLevel.ADMIN_ONLY,
            default_show_in_overview=False,
        )

        updated = update_event(
            event=event,
            data=EventInput(event_type=other_type),
            participants=(),
        )

        self.assertEqual(updated.access_level, AccessLevel.AUTHENTICATED)
        self.assertTrue(updated.show_in_overview)

    def test_update_rejects_soft_deleted_event(self) -> None:
        event = create_event(data=EventInput(event_type=self.event_type))
        Event.objects.filter(pk=event.pk).update(deleted_at=timezone.now())

        with self.assertRaises(ValidationError) as context:
            update_event(
                event=event,
                data=EventInput(event_type=self.event_type),
                participants=(),
            )

        self.assert_error_code(
            context,
            key="event",
            code="event_deleted",
        )

    def test_update_type_and_participants_roll_back_together(self) -> None:
        event = create_event(
            data=EventInput(event_type=self.event_type, title="Původní"),
            participants=(self.participant(),),
        )
        incompatible_type = EventType.objects.create(
            code="aggregate_incompatible",
            name="Nekompatibilní typ",
        )

        with self.assertRaises(ValidationError):
            update_event(
                event=event,
                data=EventInput(
                    event_type=incompatible_type,
                    title="Nesmí se uložit",
                ),
                participants=(self.participant(),),
            )

        event.refresh_from_db()
        self.assertEqual(event.event_type, self.event_type)
        self.assertEqual(event.title, "Původní")
        self.assertEqual(event.participants.get().role, self.role)

    def test_update_may_keep_same_inactive_type_but_not_switch_to_one(
        self,
    ) -> None:
        event = create_event(data=EventInput(event_type=self.event_type))
        self.event_type.is_active = False
        self.event_type.save(update_fields={"is_active"})

        kept = update_event(
            event=event,
            data=EventInput(event_type=self.event_type, title="Opravená"),
            participants=(),
        )
        self.assertEqual(kept.title, "Opravená")

        other_inactive = EventType.objects.create(
            code="aggregate_inactive",
            name="Jiný neaktivní typ",
            is_active=False,
        )
        with self.assertRaises(ValidationError) as context:
            update_event(
                event=event,
                data=EventInput(event_type=other_inactive),
                participants=(),
            )
        self.assert_error_code(
            context,
            key="event_type",
            code="event_type_inactive",
        )

    def test_create_rejects_inactive_event_type(self) -> None:
        self.event_type.is_active = False
        self.event_type.save(update_fields={"is_active"})

        with self.assertRaises(ValidationError) as context:
            create_event(data=EventInput(event_type=self.event_type))

        self.assert_error_code(
            context,
            key="event_type",
            code="event_type_inactive",
        )


class LifeEventUniquenessServiceTests(TestCase):
    def setUp(self) -> None:
        self.birth_type = EventType.objects.get(code="birth")
        self.birth_role = ParticipantRole.objects.get(code="born_person")
        self.person = Person.objects.create(first_name="Jan")

    def input(self) -> EventParticipantInput:
        return EventParticipantInput(
            person=self.person,
            role=self.birth_role,
        )

    def create_birth(self, title: str) -> Event:
        return create_event(
            data=EventInput(event_type=self.birth_type, title=title),
            participants=(self.input(),),
            require_complete=True,
        )

    def test_second_active_birth_is_rejected(self) -> None:
        first = self.create_birth("První narození")
        second = Event.objects.create(
            event_type=self.birth_type,
            title="Druhé narození",
        )

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=second,
                participants=(self.input(),),
                require_complete=True,
            )

        errors = context.exception.error_dict["participants"]
        conflict = next(
            error
            for error in errors
            if error.code == "duplicate_person_life_event"
        )
        self.assertEqual(conflict.params["conflicting_event_id"], first.pk)
        self.assertFalse(second.participants.exists())

    def test_archived_birth_still_blocks_second_birth(self) -> None:
        first = self.create_birth("Archivované narození")
        Event.objects.filter(pk=first.pk).update(archived_at=timezone.now())
        second = Event.objects.create(event_type=self.birth_type)

        with self.assertRaises(ValidationError):
            replace_event_participants(
                event=second,
                participants=(self.input(),),
            )

    def test_soft_deleted_birth_does_not_block_replacement(self) -> None:
        first = self.create_birth("Odstraněné narození")
        Event.objects.filter(pk=first.pk).update(deleted_at=timezone.now())

        second = self.create_birth("Nové narození")

        self.assertEqual(second.participants.get().person, self.person)

    def test_replacing_participants_on_same_birth_is_allowed(self) -> None:
        event = self.create_birth("Narození")

        result = replace_event_participants(
            event=event,
            participants=(self.input(),),
            require_complete=True,
        )

        self.assertEqual(len(result), 1)

    def test_deceased_role_on_funeral_does_not_count_as_death(self) -> None:
        funeral_type = EventType.objects.get(code="funeral")
        deceased_role = ParticipantRole.objects.get(code="deceased_person")
        funeral = Event.objects.create(event_type=funeral_type)
        replace_event_participants(
            event=funeral,
            participants=(
                EventParticipantInput(
                    person=self.person,
                    role=deceased_role,
                ),
            ),
            require_complete=True,
        )
        death_type = EventType.objects.get(code="death")

        death = create_event(
            data=EventInput(event_type=death_type),
            participants=(
                EventParticipantInput(
                    person=self.person,
                    role=deceased_role,
                ),
            ),
            require_complete=True,
        )

        self.assertEqual(death.participants.get().person, self.person)

    def test_second_active_death_is_rejected(self) -> None:
        death_type = EventType.objects.get(code="death")
        deceased_role = ParticipantRole.objects.get(code="deceased_person")
        participant = EventParticipantInput(
            person=self.person,
            role=deceased_role,
        )
        create_event(
            data=EventInput(event_type=death_type, title="První úmrtí"),
            participants=(participant,),
            require_complete=True,
        )

        with self.assertRaises(ValidationError) as context:
            create_event(
                data=EventInput(event_type=death_type, title="Druhé úmrtí"),
                participants=(participant,),
                require_complete=True,
            )

        self.assertIn(
            "duplicate_person_life_event",
            [
                error.code
                for error in context.exception.error_dict["participants"]
            ],
        )
        self.assertFalse(Event.objects.filter(title="Druhé úmrtí").exists())
