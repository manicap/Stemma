"""Doménové služby aplikace events."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from people.models import Person

from .models import (
    AllowedEventRole,
    Event,
    EventParticipant,
    ParticipantRole,
)

__all__ = ("EventParticipantInput", "replace_event_participants")


@dataclass(frozen=True, slots=True)
class EventParticipantInput:
    """Požadovaná účast osoby v události."""

    person: Person
    role: ParticipantRole
    note: str = ""


_ErrorMap = dict[str, list[ValidationError]]


def _available_params(**values: object) -> dict[str, object]:
    return {
        name: value
        for name, value in values.items()
        if value is not None
    }


def _add_error(
    errors: _ErrorMap,
    key: str,
    message: str,
    code: str,
    **params: object,
) -> None:
    errors.setdefault(key, []).append(
        ValidationError(
            message,
            code=code,
            params=_available_params(**params),
        )
    )


def _raise_event_unsaved() -> None:
    raise ValidationError(
        {
            "event": [
                ValidationError(
                    "Událost musí být uložená v databázi.",
                    code="event_unsaved",
                )
            ]
        }
    )


def _validate_participant_inputs(
    *,
    inputs: list[EventParticipantInput],
    people_by_id: dict[int, Person],
    roles_by_id: dict[int, ParticipantRole],
    rules: list[AllowedEventRole],
    require_complete: bool,
) -> None:
    errors: _ErrorMap = {}
    active_rules = {
        rule.participant_role_id: rule
        for rule in rules
        if rule.is_active
    }
    seen_pairs: dict[tuple[int, int], int] = {}
    role_counts: Counter[int] = Counter()

    for index, item in enumerate(inputs):
        person_id = item.person.pk
        role_id = item.role.pk
        person_exists = (
            person_id is not None and person_id in people_by_id
        )
        role = roles_by_id.get(role_id) if role_id is not None else None
        role_code = (
            role.code if role is not None else getattr(item.role, "code", None)
        )

        if not person_exists:
            _add_error(
                errors,
                "participants",
                "Osoba účastníka musí být uložená v databázi.",
                "participant_person_unsaved",
                index=index,
                person_id=person_id,
            )

        if role is None:
            _add_error(
                errors,
                "participants",
                "Role účastníka musí být uložená v databázi.",
                "participant_role_unsaved",
                index=index,
                role_id=role_id,
                role_code=role_code,
            )
        elif not role.is_active:
            _add_error(
                errors,
                "participants",
                "Role účastníka není aktivní.",
                "participant_role_inactive",
                index=index,
                role_id=role_id,
                role_code=role.code,
            )
        elif role_id not in active_rules:
            _add_error(
                errors,
                "participants",
                "Role není pro tento typ události aktivně povolena.",
                "role_not_allowed_for_event_type",
                index=index,
                role_id=role_id,
                role_code=role.code,
            )

        if role_id is not None:
            role_counts[role_id] += 1

        if person_id is None or role_id is None:
            continue

        pair = (person_id, role_id)
        if pair in seen_pairs:
            _add_error(
                errors,
                "participants",
                "Stejná osoba a role jsou ve vstupu uvedeny opakovaně.",
                "duplicate_event_person_role",
                index=index,
                person_id=person_id,
                role_id=role_id,
                role_code=role_code,
            )
        else:
            seen_pairs[pair] = index

    for role_id, count in role_counts.items():
        rule = active_rules.get(role_id)
        role = roles_by_id.get(role_id)
        if (
            rule is None
            or role is None
            or not role.is_active
            or rule.max_count is None
            or count <= rule.max_count
        ):
            continue
        _add_error(
            errors,
            "participants",
            "Počet účastníků v roli překračuje povolené maximum.",
            "participant_count_above_maximum",
            role_id=role_id,
            role_code=role.code,
            count=count,
            maximum=rule.max_count,
        )

    if require_complete:
        for rule in active_rules.values():
            if rule.min_count == 0:
                continue

            role = roles_by_id[rule.participant_role_id]
            count = role_counts[rule.participant_role_id]
            if not role.is_active:
                _add_error(
                    errors,
                    "participants",
                    "Povinná role účastníka není aktivní.",
                    "participant_role_inactive",
                    role_id=role.pk,
                    role_code=role.code,
                )
            elif count < rule.min_count:
                _add_error(
                    errors,
                    "participants",
                    "Počet účastníků v roli nedosahuje povinného minima.",
                    "participant_count_below_minimum",
                    role_id=role.pk,
                    role_code=role.code,
                    count=count,
                    minimum=rule.min_count,
                )

    if errors:
        raise ValidationError(errors)


def replace_event_participants(
    *,
    event: Event,
    participants: Iterable[EventParticipantInput],
    require_complete: bool = False,
) -> list[EventParticipant]:
    """Atomicky nahraď celou sadu účastníků jedné události."""

    if event.pk is None:
        _raise_event_unsaved()

    inputs = list(participants)

    with transaction.atomic():
        try:
            locked_event = (
                Event.objects.select_for_update()
                .select_related("event_type")
                .get(pk=event.pk)
            )
        except Event.DoesNotExist:
            _raise_event_unsaved()

        existing_participants = list(
            EventParticipant.objects.select_for_update()
            .filter(event=locked_event)
            .order_by("pk")
        )

        person_ids = sorted(
            {
                item.person.pk
                for item in inputs
                if item.person.pk is not None
            }
        )
        people_by_id = {
            person.pk: person
            for person in Person.objects.select_for_update()
            .filter(pk__in=person_ids)
            .order_by("pk")
        }

        input_role_ids = {
            item.role.pk
            for item in inputs
            if item.role.pk is not None
        }
        roles_by_id = {
            role.pk: role
            for role in ParticipantRole.objects.select_for_update()
            .filter(pk__in=sorted(input_role_ids))
            .order_by("pk")
        }

        rules = list(
            AllowedEventRole.objects.select_for_update()
            .filter(event_type_id=locked_event.event_type_id)
            .order_by("pk")
        )
        configured_role_ids = {
            rule.participant_role_id for rule in rules
        }
        additional_role_ids = configured_role_ids - roles_by_id.keys()
        roles_by_id.update(
            {
                role.pk: role
                for role in ParticipantRole.objects.select_for_update()
                .filter(pk__in=sorted(additional_role_ids))
                .order_by("pk")
            }
        )

        _validate_participant_inputs(
            inputs=inputs,
            people_by_id=people_by_id,
            roles_by_id=roles_by_id,
            rules=rules,
            require_complete=require_complete,
        )

        desired_by_key = {
            (item.person.pk, item.role.pk): item for item in inputs
        }
        existing_by_key = {
            (participant.person_id, participant.role_id): participant
            for participant in existing_participants
        }

        for key, participant in existing_by_key.items():
            if key not in desired_by_key:
                participant.delete()

        for key, item in desired_by_key.items():
            existing = existing_by_key.get(key)
            if existing is not None:
                if existing.note != item.note:
                    existing.note = item.note
                    existing.save(update_fields={"note"})
                continue

            person_id, role_id = key
            EventParticipant.objects.create(
                event=locked_event,
                person=people_by_id[person_id],
                role=roles_by_id[role_id],
                note=item.note,
            )

        return list(
            EventParticipant.objects.filter(event=locked_event)
            .select_related("event", "person", "role")
        )
