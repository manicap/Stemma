"""Actor-aware birth and death event write boundary."""

from dataclasses import replace
from typing import NoReturn

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from common.permissions import (
    can_view_access_level,
    require_active_actor_permission,
)
from people.models import Person
from places.models import Place

from .models import Event, EventParticipant, EventType, ParticipantRole
from .services import (
    EventInput,
    EventParticipantInput,
    create_event,
    update_event,
)

__all__ = (
    "create_person_life_event",
    "get_person_life_event_for_update",
    "update_person_life_event",
)

_LIFE_EVENT_ROLES = {
    "birth": "born_person",
    "death": "deceased_person",
}


def _raise_life_event_error(
    key: str,
    message: str,
    code: str,
) -> NoReturn:
    raise ValidationError({key: ValidationError(message, code=code)})


def _permission_for(*, updating: bool) -> str:
    return "events.change_event" if updating else "events.add_event"


def _require_actor(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    updating: bool,
) -> AbstractBaseUser:
    return require_active_actor_permission(
        actor=actor,
        permission=_permission_for(updating=updating),
        denial_message="K zápisu této události nemáte oprávnění.",
    )


def _load_person(person: Person) -> Person:
    if not isinstance(person, Person) or person.pk is None:
        raise Person.DoesNotExist
    try:
        return Person.objects.select_for_update().get(pk=person.pk)
    except Person.DoesNotExist:
        raise Person.DoesNotExist from None


def _authorize_person(*, person: Person, actor: AbstractBaseUser) -> None:
    if (
        person.archived_at is not None
        or person.deleted_at is not None
        or not can_view_access_level(
            actor=actor,
            access_level=person.access_level,
        )
    ):
        raise Person.DoesNotExist


def _load_life_event_type(event_type_code: str) -> EventType:
    if event_type_code not in _LIFE_EVENT_ROLES:
        _raise_life_event_error(
            "event_type",
            "Toto rozhraní podporuje pouze narození a úmrtí.",
            "life_event_type_unsupported",
        )
    try:
        return EventType.objects.select_for_update().get(
            code=event_type_code,
            is_system=True,
        )
    except EventType.DoesNotExist:
        _raise_life_event_error(
            "event_type",
            "Požadovaný systémový typ události není dostupný.",
            "life_event_type_unavailable",
        )


def _load_life_event_role(event_type_code: str) -> ParticipantRole:
    role_code = _LIFE_EVENT_ROLES[event_type_code]
    try:
        return ParticipantRole.objects.select_for_update().get(
            code=role_code,
            is_active=True,
            is_system=True,
        )
    except ParticipantRole.DoesNotExist:
        _raise_life_event_error(
            "participants",
            "Požadovaná systémová role události není dostupná.",
            "life_event_role_unavailable",
        )


def _load_place(place: Place | None) -> Place | None:
    if place is None:
        return None
    if not isinstance(place, Place) or place.pk is None:
        _raise_life_event_error(
            "place",
            "Místo musí být uložené a existovat v databázi.",
            "life_event_place_unsaved",
        )
    try:
        return Place.objects.select_for_update().get(pk=place.pk)
    except Place.DoesNotExist:
        _raise_life_event_error(
            "place",
            "Místo musí být uložené a existovat v databázi.",
            "life_event_place_unsaved",
        )


def _authorize_place(
    *,
    place: Place | None,
    actor: AbstractBaseUser,
    hide_existence: bool,
) -> None:
    if place is None:
        return
    accessible = (
        place.archived_at is None
        and place.deleted_at is None
        and can_view_access_level(
            actor=actor,
            access_level=place.access_level,
        )
    )
    if accessible:
        return
    if hide_existence:
        raise Event.DoesNotExist
    raise PermissionDenied("K použití tohoto místa nemáte oprávnění.")


def _authorize_event(
    *,
    event: Event,
    person: Person,
    actor: AbstractBaseUser,
    event_type_code: str,
    participants: list[EventParticipant],
) -> None:
    expected_role_code = _LIFE_EVENT_ROLES[event_type_code]
    has_target = any(
        participant.person_id == person.pk
        and participant.role.code == expected_role_code
        for participant in participants
    )
    if (
        event.archived_at is not None
        or event.deleted_at is not None
        or event.event_type.code != event_type_code
        or not event.event_type.is_system
        or not has_target
        or not can_view_access_level(
            actor=actor,
            access_level=event.access_level,
        )
    ):
        raise Event.DoesNotExist
    for participant in participants:
        participant_person = participant.person
        if (
            participant_person.archived_at is not None
            or participant_person.deleted_at is not None
            or not can_view_access_level(
                actor=actor,
                access_level=participant_person.access_level,
            )
        ):
            raise Event.DoesNotExist
    _authorize_place(
        place=event.place,
        actor=actor,
        hide_existence=True,
    )


def _load_event_context(
    *,
    event: Event,
    person: Person,
    actor: AbstractBaseUser,
    event_type_code: str,
) -> tuple[Event, list[EventParticipant]]:
    if not isinstance(event, Event) or event.pk is None:
        raise Event.DoesNotExist
    try:
        candidate = (
            Event.objects.select_for_update()
            .select_related("event_type", "place")
            .get(pk=event.pk)
        )
    except Event.DoesNotExist:
        raise Event.DoesNotExist from None
    participants = list(
        EventParticipant.objects.select_for_update()
        .filter(event=candidate)
        .select_related("person", "role")
        .order_by("pk")
    )
    _authorize_event(
        event=candidate,
        person=person,
        actor=actor,
        event_type_code=event_type_code,
        participants=participants,
    )
    return candidate, participants


def _authorize_proposed_data(
    *,
    data: EventInput,
    place: Place | None,
    actor: AbstractBaseUser,
) -> None:
    if not can_view_access_level(
        actor=actor,
        access_level=data.access_level,
    ):
        raise PermissionDenied(
            "K nastavení této úrovně přístupu nemáte oprávnění."
        )
    _authorize_place(place=place, actor=actor, hide_existence=False)


def _duplicate_life_event_exists(
    *,
    person: Person,
    event_type_code: str,
) -> bool:
    return EventParticipant.objects.select_for_update().filter(
        person=person,
        role__code=_LIFE_EVENT_ROLES[event_type_code],
        event__event_type__code=event_type_code,
        event__deleted_at__isnull=True,
    ).exists()


@transaction.atomic
def create_person_life_event(
    *,
    person: Person,
    event_type_code: str,
    data: EventInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Event:
    """Create one authorized birth or death aggregate for a person."""

    current_actor = _require_actor(actor=actor, updating=False)
    current_person = _load_person(person)
    _authorize_person(person=current_person, actor=current_actor)
    event_type = _load_life_event_type(event_type_code)
    role = _load_life_event_role(event_type_code)
    if not event_type.is_active:
        _raise_life_event_error(
            "event_type",
            "Neaktivní typ nelze použít pro novou událost.",
            "life_event_type_inactive",
        )
    if _duplicate_life_event_exists(
        person=current_person,
        event_type_code=event_type_code,
    ):
        raise PermissionDenied("Událost nelze vytvořit.")
    place = _load_place(data.place)
    _authorize_proposed_data(data=data, place=place, actor=current_actor)
    current_actor = _require_actor(actor=actor, updating=False)
    return create_event(
        data=replace(data, event_type=event_type, place=place),
        participants=(
            EventParticipantInput(person=current_person, role=role),
        ),
        created_by=current_actor,
        require_complete=True,
    )


@transaction.atomic
def get_person_life_event_for_update(
    *,
    person: Person,
    event: Event,
    event_type_code: str,
    actor: AbstractBaseUser | AnonymousUser,
) -> Event:
    """Return one currently editable life event without exposing hidden state."""

    current_actor = _require_actor(actor=actor, updating=True)
    current_person = _load_person(person)
    _authorize_person(person=current_person, actor=current_actor)
    candidate, _participants = _load_event_context(
        event=event,
        person=current_person,
        actor=current_actor,
        event_type_code=event_type_code,
    )
    return candidate


@transaction.atomic
def update_person_life_event(
    *,
    person: Person,
    event: Event,
    event_type_code: str,
    data: EventInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Event:
    """Update one authorized life event and preserve every participant."""

    current_actor = _require_actor(actor=actor, updating=True)
    current_person = _load_person(person)
    _authorize_person(person=current_person, actor=current_actor)
    candidate, participants = _load_event_context(
        event=event,
        person=current_person,
        actor=current_actor,
        event_type_code=event_type_code,
    )
    place = _load_place(data.place)
    _authorize_proposed_data(data=data, place=place, actor=current_actor)
    current_actor = _require_actor(actor=actor, updating=True)
    participant_inputs = tuple(
        EventParticipantInput(
            person=participant.person,
            role=participant.role,
            note=participant.note,
        )
        for participant in participants
    )
    return update_event(
        event=candidate,
        data=replace(
            data,
            event_type=candidate.event_type,
            place=place,
        ),
        participants=participant_inputs,
        require_complete=True,
    )
