"""Transakční doménové služby zdravotních záznamů."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from common.permissions import can_view_access_level
from people.models import Person
from places.models import Place

from .models import HealthRecord, HealthRecordType
from .permissions import (
    can_view_health_record_access,
    get_health_record_visibility_filter,
)

__all__ = (
    "HealthRecordInput",
    "create_health_record",
    "update_health_record",
)


@dataclass(frozen=True, slots=True)
class HealthRecordInput:
    """Úplný snapshot editovatelných údajů zdravotního záznamu."""

    person: Person
    record_type: HealthRecordType
    place: Place | None = None
    title: str = ""
    description: str = ""
    provider_name: str = ""
    note: str = ""
    access_level: str = AccessLevel.RESTRICTED
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


def _raise_error(key: str, message: str, code: str) -> NoReturn:
    raise ValidationError({key: ValidationError(message, code=code)})


def _load(model, value, *, key: str, label: str):
    if not isinstance(value, model) or value.pk is None:
        _raise_error(
            key,
            f"{label} musí být uložený a existovat v databázi.",
            f"health_{key}_unsaved",
        )
    try:
        return model._default_manager.select_for_update().get(pk=value.pk)
    except model.DoesNotExist:
        _raise_error(
            key,
            f"{label} musí být uložený a existovat v databázi.",
            f"health_{key}_unsaved",
        )


def _load_place(place: Place | None) -> Place | None:
    if place is None:
        return None
    return _load(Place, place, key="place", label="Místo")


def _load_actor(
    actor: AbstractBaseUser | AnonymousUser,
    *,
    permission: str,
) -> AbstractBaseUser:
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
    ):
        raise PermissionDenied(
            "K zápisu zdravotního záznamu nemáte oprávnění."
        )
    try:
        current_actor = user_model._default_manager.get(pk=actor.pk)
    except user_model.DoesNotExist as error:
        raise PermissionDenied(
            "K zápisu zdravotního záznamu nemáte oprávnění."
        ) from error
    if not current_actor.is_active or not current_actor.has_perm(permission):
        raise PermissionDenied(
            "K zápisu zdravotního záznamu nemáte oprávnění."
        )
    return current_actor


def _authorize_write_access(
    *,
    actor: AbstractBaseUser,
    person: Person,
    health_access_level: str,
) -> None:
    if (
        person.archived_at is not None
        or person.deleted_at is not None
        or not can_view_access_level(
            actor=actor,
            access_level=person.access_level,
        )
    ):
        raise Person.DoesNotExist
    if not can_view_health_record_access(
        actor=actor,
        access_level=health_access_level,
    ):
        raise PermissionDenied(
            "K zápisu zdravotního záznamu nemáte oprávnění."
        )


def _apply_input(
    record: HealthRecord,
    *,
    data: HealthRecordInput,
    person: Person,
    record_type: HealthRecordType,
    place: Place | None,
) -> None:
    record.person = person
    record.record_type = record_type
    record.place = place
    record.title = data.title.strip()
    record.description = data.description.strip()
    record.provider_name = data.provider_name.strip()
    record.note = data.note.strip()
    record.access_level = data.access_level
    record.verification_status = data.verification_status
    record.date_precision = data.date_precision
    record.date_qualifier = data.date_qualifier
    record.start_year = data.start_year
    record.start_month = data.start_month
    record.start_day = data.start_day
    record.end_year = data.end_year
    record.end_month = data.end_month
    record.end_day = data.end_day
    record.original_date_text = data.original_date_text.strip()
    record.date_note = data.date_note.strip()


def _reload(record_id: int) -> HealthRecord:
    return HealthRecord.objects.select_related(
        "person",
        "record_type",
        "place",
        "created_by",
    ).get(pk=record_id)


def create_health_record(
    *,
    data: HealthRecordInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Atomicky vytvoř a vrať čerstvě načtený zdravotní záznam."""

    with transaction.atomic():
        current_actor = _load_actor(
            actor,
            permission="health.add_healthrecord",
        )
        person = _load(Person, data.person, key="person", label="Osoba")
        record_type = _load(
            HealthRecordType,
            data.record_type,
            key="record_type",
            label="Typ zdravotního záznamu",
        )
        place = _load_place(data.place)
        if not record_type.is_active:
            _raise_error(
                "record_type",
                "Neaktivní typ nelze použít pro nový zdravotní záznam.",
                "health_record_type_inactive",
            )
        _authorize_write_access(
            actor=current_actor,
            person=person,
            health_access_level=data.access_level,
        )

        candidate = HealthRecord(created_by=current_actor)
        _apply_input(
            candidate,
            data=data,
            person=person,
            record_type=record_type,
            place=place,
        )
        candidate.full_clean()
        candidate.save()
        return _reload(candidate.pk)


def update_health_record(
    *,
    health_record: HealthRecord,
    data: HealthRecordInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Atomicky změň a vrať čerstvě načtený zdravotní záznam."""

    with transaction.atomic():
        current_actor = _load_actor(
            actor,
            permission="health.change_healthrecord",
        )
        if (
            not isinstance(health_record, HealthRecord)
            or health_record.pk is None
        ):
            _raise_error(
                "health_record",
                "Zdravotní záznam musí být uložený a existovat v databázi.",
                "health_record_unsaved",
            )
        candidate = (
            HealthRecord.objects.select_for_update()
            .filter(get_health_record_visibility_filter(actor=current_actor))
            .get(pk=health_record.pk)
        )

        person = _load(Person, data.person, key="person", label="Osoba")
        record_type = _load(
            HealthRecordType,
            data.record_type,
            key="record_type",
            label="Typ zdravotního záznamu",
        )
        place = _load_place(data.place)
        if not record_type.is_active:
            _raise_error(
                "record_type",
                "Neaktivní typ nelze použít při změně zdravotního záznamu.",
                "health_record_type_inactive",
            )
        _authorize_write_access(
            actor=current_actor,
            person=person,
            health_access_level=data.access_level,
        )

        _apply_input(
            candidate,
            data=data,
            person=person,
            record_type=record_type,
            place=place,
        )
        candidate.full_clean()
        candidate.save()
        return _reload(candidate.pk)
