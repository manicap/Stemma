from dataclasses import FrozenInstanceError, is_dataclass
from inspect import Parameter, signature
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from people.models import Person

from .models import (
    AllowedEventRole,
    Event,
    EventParticipant,
    EventType,
    ParticipantRole,
)
from .services import EventParticipantInput, replace_event_participants


class EventParticipantServiceApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu služby účastníků."""

    def test_input_is_frozen_slotted_dataclass_with_empty_note(self) -> None:
        person = Person(first_name="Jan")
        role = ParticipantRole(code="subject", name="Hlavní osoba")
        participant = EventParticipantInput(person=person, role=role)

        self.assertTrue(is_dataclass(EventParticipantInput))
        self.assertTrue(EventParticipantInput.__dataclass_params__.frozen)
        self.assertEqual(
            EventParticipantInput.__slots__,
            ("person", "role", "note"),
        )
        self.assertFalse(hasattr(participant, "__dict__"))
        self.assertEqual(participant.note, "")

        with self.assertRaises(FrozenInstanceError):
            participant.note = "Změna"

    def test_replace_contract_is_keyword_only(self) -> None:
        parameters = signature(replace_event_participants).parameters

        self.assertEqual(
            tuple(parameters),
            ("event", "participants", "require_complete"),
        )
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )
        self.assertIs(parameters["require_complete"].default, False)


class EventParticipantServiceTests(TestCase):
    """Ověření atomické náhrady a validace účastníků události."""

    def setUp(self) -> None:
        self.event_type = EventType.objects.create(
            code="service_event",
            name="Servisní událost",
        )
        self.event = Event.objects.create(
            event_type=self.event_type,
            title="Test služby",
        )
        self.primary_role = ParticipantRole.objects.create(
            code="service_primary",
            name="Hlavní servisní role",
            sort_order=10,
        )
        self.unlimited_role = ParticipantRole.objects.create(
            code="service_unlimited",
            name="Neomezená servisní role",
            sort_order=20,
        )
        self.disallowed_role = ParticipantRole.objects.create(
            code="service_disallowed",
            name="Nepovolená servisní role",
            sort_order=30,
        )
        self.primary_rule = AllowedEventRole.objects.create(
            event_type=self.event_type,
            participant_role=self.primary_role,
            min_count=1,
            max_count=2,
            sort_order=10,
        )
        self.unlimited_rule = AllowedEventRole.objects.create(
            event_type=self.event_type,
            participant_role=self.unlimited_role,
            min_count=0,
            max_count=None,
            sort_order=20,
        )
        self.people = [
            Person.objects.create(first_name="Jan", last_name="Novák"),
            Person.objects.create(first_name="Petr", last_name="Novák"),
            Person.objects.create(first_name="Adam", last_name="Beneš"),
            Person.objects.create(first_name="Eva", last_name="Černá"),
        ]

    def participant_input(
        self,
        person: Person,
        role: ParticipantRole | None = None,
        note: str = "",
    ) -> EventParticipantInput:
        return EventParticipantInput(
            person=person,
            role=role or self.primary_role,
            note=note,
        )

    def assert_error(
        self,
        context,
        *,
        key: str,
        code: str,
    ) -> ValidationError:
        self.assertTrue(
            set(context.exception.error_dict).issubset(
                {"event", "participants"}
            )
        )
        errors = context.exception.error_dict[key]
        matching = [error for error in errors if error.code == code]
        self.assertTrue(matching, f"Chybí kód {code!r} pod klíčem {key!r}.")
        return matching[0]

    def test_input_iterable_is_materialized_once(self) -> None:
        service_input = self.participant_input(self.people[0])

        class SingleUseIterable:
            def __init__(self) -> None:
                self.iterations = 0

            def __iter__(self):
                self.iterations += 1
                if self.iterations > 1:
                    raise AssertionError("Iterable byl vyhodnocen opakovaně.")
                return iter((service_input,))

        participants = SingleUseIterable()

        result = replace_event_participants(
            event=self.event,
            participants=participants,
        )

        self.assertEqual(participants.iterations, 1)
        self.assertEqual(len(result), 1)

    def test_creates_one_valid_participant(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[self.participant_input(self.people[0])],
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].person, self.people[0])
        self.assertEqual(result[0].role, self.primary_role)

    def test_creates_multiple_participants_in_different_roles(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(self.people[0]),
                self.participant_input(
                    self.people[1],
                    self.unlimited_role,
                ),
            ],
        )

        self.assertEqual(len(result), 2)

    def test_allows_multiple_people_in_unlimited_role(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(person, self.unlimited_role)
                for person in self.people
            ],
        )

        self.assertEqual(len(result), len(self.people))

    def test_allows_same_person_in_different_roles(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(self.people[0]),
                self.participant_input(
                    self.people[0],
                    self.unlimited_role,
                ),
            ],
        )

        self.assertEqual(len(result), 2)

    def test_replaces_whole_participant_set(self) -> None:
        old = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
        )

        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(
                    self.people[1],
                    self.unlimited_role,
                )
            ],
        )

        self.assertFalse(
            EventParticipant.objects.filter(pk=old.pk).exists()
        )
        self.assertEqual([item.person for item in result], [self.people[1]])

    def test_empty_set_removes_participant(self) -> None:
        EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
        )

        result = replace_event_participants(
            event=self.event,
            participants=[],
        )

        self.assertEqual(result, [])
        self.assertFalse(self.event.participants.exists())

    def test_note_update_preserves_participant_primary_key(self) -> None:
        existing = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
            note="Původní poznámka",
        )

        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(
                    self.people[0],
                    note="Nová poznámka",
                )
            ],
        )

        self.assertEqual(result[0].pk, existing.pk)
        self.assertEqual(result[0].note, "Nová poznámka")

    def test_returns_model_ordering(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(
                    self.people[0],
                    self.unlimited_role,
                ),
                self.participant_input(self.people[1]),
                self.participant_input(self.people[2]),
            ],
        )

        self.assertEqual(
            [(item.role_id, item.person_id) for item in result],
            [
                (self.primary_role.pk, self.people[2].pk),
                (self.primary_role.pk, self.people[1].pk),
                (self.unlimited_role.pk, self.people[0].pk),
            ],
        )

    def test_uses_current_event_type_from_database(self) -> None:
        current_type = EventType.objects.create(
            code="service_current_type",
            name="Aktuální typ z databáze",
        )
        Event.objects.filter(pk=self.event.pk).update(
            event_type=current_type
        )
        self.assertEqual(self.event.event_type_id, self.event_type.pk)

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0])],
            )

        self.assert_error(
            context,
            key="participants",
            code="role_not_allowed_for_event_type",
        )

    def test_allows_archived_and_soft_deleted_people(self) -> None:
        now = timezone.now()
        Person.objects.filter(pk=self.people[0].pk).update(archived_at=now)
        Person.objects.filter(pk=self.people[1].pk).update(deleted_at=now)

        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(self.people[0]),
                self.participant_input(self.people[1]),
            ],
        )

        self.assertEqual(len(result), 2)

    def test_does_not_reject_event_lifecycle_state(self) -> None:
        Event.objects.filter(pk=self.event.pk).update(
            deleted_at=timezone.now()
        )

        result = replace_event_participants(
            event=self.event,
            participants=[self.participant_input(self.people[0])],
        )

        self.assertEqual(len(result), 1)

    def test_rejects_unsaved_event(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=Event(event_type=self.event_type),
                participants=[],
            )

        self.assert_error(context, key="event", code="event_unsaved")

    def test_rejects_event_missing_from_database(self) -> None:
        missing_event = Event.objects.create(event_type=self.event_type)
        missing_pk = missing_event.pk
        missing_event.delete()
        missing_event.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=missing_event,
                participants=[],
            )

        self.assert_error(context, key="event", code="event_unsaved")

    def test_rejects_unsaved_person_with_index_param(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(Person(first_name="Nová"))
                ],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_person_unsaved",
        )
        self.assertEqual(error.params, {"index": 0})

    def test_rejects_person_missing_from_database(self) -> None:
        missing_person = Person.objects.create(first_name="Dočasná")
        missing_pk = missing_person.pk
        missing_person.delete()
        missing_person.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(missing_person)],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_person_unsaved",
        )
        self.assertEqual(
            error.params,
            {"index": 0, "person_id": missing_pk},
        )

    def test_rejects_unsaved_role(self) -> None:
        role = ParticipantRole(code="unsaved", name="Neuložená")

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0], role)],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_role_unsaved",
        )
        self.assertEqual(
            error.params,
            {"index": 0, "role_code": "unsaved"},
        )

    def test_rejects_role_missing_from_database(self) -> None:
        role = ParticipantRole.objects.create(
            code="deleted_role",
            name="Smazaná role",
        )
        role_pk = role.pk
        role.delete()
        role.pk = role_pk

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0], role)],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_role_unsaved",
        )
        self.assertEqual(
            error.params,
            {
                "index": 0,
                "role_id": role_pk,
                "role_code": "deleted_role",
            },
        )

    def test_rejects_inactive_role_using_current_database_state(self) -> None:
        ParticipantRole.objects.filter(pk=self.primary_role.pk).update(
            is_active=False
        )
        self.assertTrue(self.primary_role.is_active)

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0])],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_role_inactive",
        )
        self.assertEqual(error.params["index"], 0)
        self.assertEqual(error.params["role_id"], self.primary_role.pk)

    def test_rejects_role_not_allowed_for_event_type(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(
                        self.people[0],
                        self.disallowed_role,
                    )
                ],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="role_not_allowed_for_event_type",
        )
        self.assertEqual(error.params["index"], 0)
        self.assertEqual(error.params["role_code"], "service_disallowed")

    def test_rejects_inactive_allowed_rule_using_database_state(self) -> None:
        AllowedEventRole.objects.filter(pk=self.primary_rule.pk).update(
            is_active=False
        )
        self.assertTrue(self.primary_rule.is_active)

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0])],
            )

        self.assert_error(
            context,
            key="participants",
            code="role_not_allowed_for_event_type",
        )

    def test_rejects_active_rule_with_inactive_required_role(self) -> None:
        ParticipantRole.objects.filter(pk=self.primary_role.pk).update(
            is_active=False
        )

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[],
                require_complete=True,
            )

        self.assert_error(
            context,
            key="participants",
            code="participant_role_inactive",
        )

    def test_rejects_duplicate_person_and_role(self) -> None:
        duplicate = self.participant_input(self.people[0])

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[duplicate, duplicate],
            )

        error = self.assert_error(
            context,
            key="participants",
            code="duplicate_event_person_role",
        )
        self.assertEqual(error.params["index"], 1)

    def test_different_note_does_not_allow_duplicate(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(self.people[0], note="První"),
                    self.participant_input(self.people[0], note="Druhá"),
                ],
            )

        self.assert_error(
            context,
            key="participants",
            code="duplicate_event_person_role",
        )

    def test_count_below_maximum_is_allowed(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[self.participant_input(self.people[0])],
        )

        self.assertEqual(len(result), 1)

    def test_count_equal_to_maximum_is_allowed(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(self.people[0]),
                self.participant_input(self.people[1]),
            ],
        )

        self.assertEqual(len(result), 2)

    def test_count_above_maximum_is_rejected_when_incomplete(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(self.people[0]),
                    self.participant_input(self.people[1]),
                    self.participant_input(self.people[2]),
                ],
                require_complete=False,
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_count_above_maximum",
        )
        self.assertEqual(
            error.params,
            {
                "role_id": self.primary_role.pk,
                "role_code": "service_primary",
                "count": 3,
                "maximum": 2,
            },
        )

    def test_unlimited_maximum_allows_many_people(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(person, self.unlimited_role)
                for person in self.people
            ],
        )

        self.assertEqual(len(result), 4)

    def test_incomplete_mode_allows_missing_required_role(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[],
            require_complete=False,
        )

        self.assertEqual(result, [])

    def test_complete_mode_rejects_count_below_minimum(self) -> None:
        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[],
                require_complete=True,
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_count_below_minimum",
        )
        self.assertEqual(
            error.params,
            {
                "role_id": self.primary_role.pk,
                "role_code": "service_primary",
                "count": 0,
                "minimum": 1,
            },
        )

    def test_complete_mode_accepts_exact_minimum(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[self.participant_input(self.people[0])],
            require_complete=True,
        )

        self.assertEqual(len(result), 1)

    def test_complete_mode_accepts_above_minimum_within_maximum(self) -> None:
        result = replace_event_participants(
            event=self.event,
            participants=[
                self.participant_input(self.people[0]),
                self.participant_input(self.people[1]),
            ],
            require_complete=True,
        )

        self.assertEqual(len(result), 2)

    def test_complete_mode_checks_all_active_rules(self) -> None:
        second_required_role = ParticipantRole.objects.create(
            code="service_second_required",
            name="Druhá povinná role",
        )
        AllowedEventRole.objects.create(
            event_type=self.event_type,
            participant_role=second_required_role,
            min_count=1,
            max_count=None,
        )

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0])],
                require_complete=True,
            )

        error = self.assert_error(
            context,
            key="participants",
            code="participant_count_below_minimum",
        )
        self.assertEqual(error.params["role_id"], second_required_role.pk)

    def test_inactive_rule_is_excluded_from_minimum(self) -> None:
        self.primary_rule.is_active = False
        self.primary_rule.save(update_fields={"is_active"})

        result = replace_event_participants(
            event=self.event,
            participants=[],
            require_complete=True,
        )

        self.assertEqual(result, [])

    def test_configuration_change_does_not_modify_historical_record(self) -> None:
        historical = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
            note="Historická účast",
        )
        self.primary_rule.is_active = False
        self.primary_rule.save(update_fields={"is_active"})

        historical.refresh_from_db()

        self.assertEqual(historical.note, "Historická účast")

    def test_historical_participant_must_pass_current_configuration(self) -> None:
        historical = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
        )
        self.primary_rule.is_active = False
        self.primary_rule.save(update_fields={"is_active"})

        with self.assertRaises(ValidationError) as context:
            replace_event_participants(
                event=self.event,
                participants=[self.participant_input(self.people[0])],
            )

        self.assert_error(
            context,
            key="participants",
            code="role_not_allowed_for_event_type",
        )
        self.assertTrue(
            EventParticipant.objects.filter(pk=historical.pk).exists()
        )

    def test_omitting_invalid_historical_participant_removes_it(self) -> None:
        historical = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
        )
        self.primary_rule.is_active = False
        self.primary_rule.save(update_fields={"is_active"})

        replace_event_participants(event=self.event, participants=[])

        self.assertFalse(
            EventParticipant.objects.filter(pk=historical.pk).exists()
        )

    def test_note_change_of_invalid_historical_participant_is_rejected(
        self,
    ) -> None:
        historical = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
            note="Původní",
        )
        self.primary_rule.is_active = False
        self.primary_rule.save(update_fields={"is_active"})

        with self.assertRaises(ValidationError):
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(self.people[0], note="Nová")
                ],
            )

        historical.refresh_from_db()
        self.assertEqual(historical.note, "Původní")

    def test_validation_error_creates_no_participant(self) -> None:
        with self.assertRaises(ValidationError):
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(self.people[0]),
                    self.participant_input(
                        self.people[1],
                        self.disallowed_role,
                    ),
                ],
            )

        self.assertFalse(self.event.participants.exists())

    def test_invalid_replacement_keeps_original_set(self) -> None:
        original = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
            note="Původní",
        )

        with self.assertRaises(ValidationError):
            replace_event_participants(
                event=self.event,
                participants=[
                    self.participant_input(
                        self.people[1],
                        self.disallowed_role,
                    )
                ],
            )

        self.assertEqual(
            list(
                self.event.participants.values_list(
                    "pk",
                    "person_id",
                    "role_id",
                    "note",
                )
            ),
            [
                (
                    original.pk,
                    self.people[0].pk,
                    self.primary_role.pk,
                    "Původní",
                )
            ],
        )

    def test_second_write_error_rolls_back_all_changes(self) -> None:
        original = EventParticipant.objects.create(
            event=self.event,
            person=self.people[0],
            role=self.primary_role,
            note="Původní",
        )
        original_create = EventParticipant.objects.create
        create_calls = 0

        def create_then_fail(*args, **kwargs):
            nonlocal create_calls
            create_calls += 1
            if create_calls == 2:
                raise IntegrityError("Simulovaná chyba druhého zápisu.")
            return original_create(*args, **kwargs)

        with patch(
            "events.services.EventParticipant.objects.create",
            side_effect=create_then_fail,
        ):
            with self.assertRaises(IntegrityError):
                replace_event_participants(
                    event=self.event,
                    participants=[
                        self.participant_input(
                            self.people[1],
                            self.unlimited_role,
                        ),
                        self.participant_input(
                            self.people[2],
                            self.unlimited_role,
                        ),
                    ],
                )

        self.assertEqual(create_calls, 2)
        self.assertEqual(
            list(
                self.event.participants.values_list(
                    "pk",
                    "person_id",
                    "role_id",
                    "note",
                )
            ),
            [
                (
                    original.pk,
                    self.people[0].pk,
                    self.primary_role.pk,
                    "Původní",
                )
            ],
        )

    def test_service_does_not_add_model_clean_validation(self) -> None:
        self.assertIs(EventParticipant.clean, models.Model.clean)
