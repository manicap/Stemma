"""Doménové služby aplikace events."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from common.choices import (
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from people.models import Person
from places.models import Place

from .models import (
    AllowedEventRole,
    DeathDetail,
    Event,
    EventParticipant,
    EventType,
    ParticipantRole,
)

__all__ = (
    "DeathDetailInput",
    "EventInput",
    "EventParticipantInput",
    "create_death_detail",
    "create_event",
    "delete_death_detail",
    "replace_event_participants",
    "update_death_detail",
    "update_event",
)


@dataclass(frozen=True, slots=True)
class DeathDetailInput:
    """Úplný snapshot textového detailu úmrtí."""

    cause: str = ""
    circumstances: str = ""


@dataclass(frozen=True, slots=True)
class EventInput:
    """Úplný snapshot editovatelných údajů události."""

    event_type: EventType
    place: Place | None = None
    location_detail: str = ""
    title: str = ""
    description: str = ""
    show_in_overview: bool | None = None
    access_level: str | None = None
    verification_status: str = VerificationStatus.UNCONFIRMED
    date_precision: str = DatePrecision.UNKNOWN
    date_qualifier: str = DateQualifier.NONE
    start_year: int | None = None
    start_month: int | None = None
    start_day: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    end_day: int | None = None
    original_date_text: str = ""
    date_note: str = ""


@dataclass(frozen=True, slots=True)
class EventParticipantInput:
    """Požadovaná účast osoby v události."""

    person: Person
    role: ParticipantRole
    note: str = ""


_ErrorMap = dict[str, list[ValidationError]]
_LIFE_EVENT_ROLE_CODES = {
    "birth": "born_person",
    "death": "deceased_person",
}


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


def _raise_service_error(key: str, message: str, code: str) -> None:
    raise ValidationError({key: ValidationError(message, code=code)})


def _load_event_type(event_type: EventType) -> EventType:
    if event_type.pk is None:
        _raise_service_error(
            "event_type",
            "Typ události musí být uložený v databázi.",
            "event_type_unsaved",
        )
    try:
        return EventType.objects.select_for_update().get(pk=event_type.pk)
    except EventType.DoesNotExist:
        _raise_service_error(
            "event_type",
            "Typ události musí být uložený v databázi.",
            "event_type_unsaved",
        )


def _load_place(place: Place | None) -> Place | None:
    if place is None:
        return None
    if place.pk is None:
        _raise_service_error(
            "place",
            "Místo musí být uložené v databázi.",
            "event_place_unsaved",
        )
    try:
        return Place.objects.select_for_update().get(pk=place.pk)
    except Place.DoesNotExist:
        _raise_service_error(
            "place",
            "Místo musí být uložené v databázi.",
            "event_place_unsaved",
        )


def _load_created_by(
    created_by: AbstractBaseUser | None,
) -> AbstractBaseUser | None:
    if created_by is None:
        return None
    if created_by.pk is None:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "event_created_by_unsaved",
        )
    try:
        return get_user_model()._default_manager.select_for_update().get(
            pk=created_by.pk
        )
    except get_user_model().DoesNotExist:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "event_created_by_unsaved",
        )


def _apply_event_input(
    event: Event,
    *,
    data: EventInput,
    event_type: EventType,
    place: Place | None,
    creating: bool,
) -> None:
    access_level = data.access_level
    if access_level is None:
        access_level = (
            event_type.default_access_level if creating else event.access_level
        )
    show_in_overview = data.show_in_overview
    if show_in_overview is None:
        show_in_overview = (
            event_type.default_show_in_overview
            if creating
            else event.show_in_overview
        )

    event.event_type = event_type
    event.place = place
    event.location_detail = data.location_detail.strip()
    event.title = data.title.strip()
    event.description = data.description.strip()
    event.show_in_overview = show_in_overview
    event.access_level = access_level
    event.verification_status = data.verification_status
    event.date_precision = data.date_precision
    event.date_qualifier = data.date_qualifier
    event.start_year = data.start_year
    event.start_month = data.start_month
    event.start_day = data.start_day
    event.end_year = data.end_year
    event.end_month = data.end_month
    event.end_day = data.end_day
    event.original_date_text = data.original_date_text.strip()
    event.date_note = data.date_note.strip()


def _reload_event(event_id: int) -> Event:
    return Event.objects.select_related(
        "event_type", "place", "created_by"
    ).get(pk=event_id)


def _is_system_death_type(event_type: EventType) -> bool:
    return event_type.code == "death" and event_type.is_system


def _raise_death_detail_unsaved() -> None:
    _raise_service_error(
        "death_detail",
        "Detail úmrtí musí být uložený v databázi.",
        "death_detail_unsaved",
    )


def _validate_death_detail_event(
    event: Event,
    *,
    require_death_type: bool = True,
) -> None:
    if event.deleted_at is not None:
        _raise_service_error(
            "event",
            "Detail měkce odstraněné události nelze měnit.",
            "death_detail_event_deleted",
        )
    if require_death_type and not _is_system_death_type(event.event_type):
        _raise_service_error(
            "event",
            "Detail úmrtí lze připojit pouze k systémové události úmrtí.",
            "death_detail_event_type_required",
        )


def _lock_death_event(event: Event) -> Event:
    if event.pk is None:
        _raise_service_error(
            "event",
            "Událost musí být uložená v databázi.",
            "death_detail_event_unsaved",
        )
    try:
        locked_event = (
            Event.objects.select_for_update()
            .select_related("event_type")
            .get(pk=event.pk)
        )
    except Event.DoesNotExist:
        _raise_service_error(
            "event",
            "Událost musí být uložená v databázi.",
            "death_detail_event_unsaved",
        )
    _validate_death_detail_event(locked_event)
    return locked_event


def _lock_death_detail(
    detail: DeathDetail,
    *,
    require_death_type: bool = True,
) -> DeathDetail:
    if detail.pk is None:
        _raise_death_detail_unsaved()
    event_id = (
        DeathDetail.objects.filter(pk=detail.pk)
        .values_list("event_id", flat=True)
        .first()
    )
    if event_id is None:
        _raise_death_detail_unsaved()
    try:
        locked_event = (
            Event.objects.select_for_update()
            .select_related("event_type")
            .get(pk=event_id)
        )
        locked_detail = DeathDetail.objects.select_for_update().get(
            pk=detail.pk,
            event_id=event_id,
        )
    except (Event.DoesNotExist, DeathDetail.DoesNotExist):
        _raise_death_detail_unsaved()
    _validate_death_detail_event(
        locked_event,
        require_death_type=require_death_type,
    )
    return locked_detail


def _reload_death_detail(detail_id: int) -> DeathDetail:
    return DeathDetail.objects.select_related(
        "event", "event__event_type"
    ).get(pk=detail_id)


@transaction.atomic
def create_death_detail(
    *,
    event: Event,
    data: DeathDetailInput,
) -> DeathDetail:
    """Vytvoř jediný detail systémové události úmrtí."""

    locked_event = _lock_death_event(event)
    if DeathDetail.objects.select_for_update().filter(
        event=locked_event
    ).exists():
        _raise_service_error(
            "event",
            "Událost už detail úmrtí obsahuje.",
            "death_detail_exists",
        )
    detail = DeathDetail(
        event=locked_event,
        cause=data.cause.strip(),
        circumstances=data.circumstances.strip(),
    )
    # Jedinečnost 1:1 definitivně rozhoduje databáze. Přeskočení ORM unique
    # dotazu ponechá i souběžnou kolizi na níže mapovaném stabilním kódu.
    detail.full_clean(validate_unique=False)
    try:
        with transaction.atomic():
            detail.save()
    except IntegrityError as exc:
        if DeathDetail.objects.filter(event=locked_event).exists():
            error = ValidationError(
                {
                    "event": ValidationError(
                        "Událost už detail úmrtí obsahuje.",
                        code="death_detail_exists",
                    )
                }
            )
            raise error from exc
        raise
    return _reload_death_detail(detail.pk)


@transaction.atomic
def update_death_detail(
    *,
    death_detail: DeathDetail,
    data: DeathDetailInput,
) -> DeathDetail:
    """Aktualizuj texty detailu a zachovej jeho nadřazenou událost."""

    locked_detail = _lock_death_detail(death_detail)
    locked_detail.cause = data.cause.strip()
    locked_detail.circumstances = data.circumstances.strip()
    locked_detail.full_clean()
    locked_detail.save()
    return _reload_death_detail(locked_detail.pk)


@transaction.atomic
def delete_death_detail(*, death_detail: DeathDetail) -> None:
    """Explicitně odstraň detail bez odstranění nadřazené události."""

    locked_detail = _lock_death_detail(
        death_detail,
        require_death_type=False,
    )
    locked_detail.delete()


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


def _validate_unique_life_event_participation(
    *,
    event: Event,
    inputs: list[EventParticipantInput],
    roles_by_id: dict[int, ParticipantRole],
) -> None:
    """Zabraň druhému aktivnímu narození nebo úmrtí stejné osoby."""

    if event.deleted_at is not None:
        return

    expected_role_code = _LIFE_EVENT_ROLE_CODES.get(event.event_type.code)
    if expected_role_code is None:
        return

    relevant_inputs = [
        (index, item)
        for index, item in enumerate(inputs)
        if item.role.pk in roles_by_id
        and roles_by_id[item.role.pk].code == expected_role_code
        and item.person.pk is not None
    ]
    if not relevant_inputs:
        return

    person_ids = sorted({item.person.pk for _, item in relevant_inputs})
    conflicts = {
        participant.person_id: participant.event_id
        for participant in EventParticipant.objects.select_for_update()
        .filter(
            person_id__in=person_ids,
            role__code=expected_role_code,
            event__event_type__code=event.event_type.code,
            event__deleted_at__isnull=True,
        )
        .exclude(event_id=event.pk)
        .order_by("person_id", "event_id")
    }
    errors: _ErrorMap = {}
    for index, item in relevant_inputs:
        conflicting_event_id = conflicts.get(item.person.pk)
        if conflicting_event_id is None:
            continue
        _add_error(
            errors,
            "participants",
            "Osoba už má jinou aktivní událost tohoto životního typu.",
            "duplicate_person_life_event",
            index=index,
            person_id=item.person.pk,
            event_type_code=event.event_type.code,
            conflicting_event_id=conflicting_event_id,
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
        if locked_event.deleted_at is not None:
            _raise_service_error(
                "event",
                "Měkce odstraněné události nelze měnit účastníky.",
                "event_deleted",
            )

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
        _validate_unique_life_event_participation(
            event=locked_event,
            inputs=inputs,
            roles_by_id=roles_by_id,
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


@transaction.atomic
def create_event(
    *,
    data: EventInput,
    participants: Iterable[EventParticipantInput] = (),
    created_by: AbstractBaseUser | None = None,
    require_complete: bool = False,
) -> Event:
    """Atomicky vytvoř událost včetně úplné sady účastníků."""

    participant_inputs = list(participants)
    event_type = _load_event_type(data.event_type)
    if not event_type.is_active:
        _raise_service_error(
            "event_type",
            "Typ události není aktivní.",
            "event_type_inactive",
        )
    place = _load_place(data.place)
    author = _load_created_by(created_by)

    event = Event(created_by=author)
    _apply_event_input(
        event,
        data=data,
        event_type=event_type,
        place=place,
        creating=True,
    )
    event.full_clean()
    event.save()
    replace_event_participants(
        event=event,
        participants=participant_inputs,
        require_complete=require_complete,
    )
    return _reload_event(event.pk)


@transaction.atomic
def update_event(
    *,
    event: Event,
    data: EventInput,
    participants: Iterable[EventParticipantInput],
    require_complete: bool = False,
) -> Event:
    """Atomicky nahraď údaje události i její úplnou sadu účastníků."""

    if event.pk is None:
        _raise_event_unsaved()
    participant_inputs = list(participants)
    try:
        locked_event = (
            Event.objects.select_for_update()
            .select_related("event_type")
            .get(pk=event.pk)
        )
    except Event.DoesNotExist:
        _raise_event_unsaved()
    if locked_event.deleted_at is not None:
        _raise_service_error(
            "event",
            "Měkce odstraněnou událost nelze upravit.",
            "event_deleted",
        )

    event_type = _load_event_type(data.event_type)
    if (
        not event_type.is_active
        and event_type.pk != locked_event.event_type_id
    ):
        _raise_service_error(
            "event_type",
            "Typ události není aktivní.",
            "event_type_inactive",
        )
    if (
        DeathDetail.objects.filter(event=locked_event).exists()
        and not _is_system_death_type(event_type)
    ):
        _raise_service_error(
            "event_type",
            "Událost s detailem úmrtí musí zůstat systémovou událostí úmrtí.",
            "death_detail_event_type_required",
        )
    place = _load_place(data.place)
    _apply_event_input(
        locked_event,
        data=data,
        event_type=event_type,
        place=place,
        creating=False,
    )
    locked_event.full_clean()
    locked_event.save()
    replace_event_participants(
        event=locked_event,
        participants=participant_inputs,
        require_complete=require_complete,
    )
    return _reload_event(locked_event.pk)
