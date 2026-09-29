"""Transakční doménové služby zdravotních záznamů."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from common.permissions import (
    can_view_access_level,
    require_active_actor_permission,
)
from people.models import Person
from places.models import Place

from .models import HealthRecord, HealthRecordType
from .permissions import (
    can_view_health_record_access,
    get_health_record_visibility_filter,
)

__all__ = (
    "HealthRecordInput",
    "archive_health_record",
    "create_health_record",
    "restore_archived_health_record",
    "restore_soft_deleted_health_record",
    "soft_delete_health_record",
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


def _load_lifecycle_target(
    *,
    health_record: HealthRecord,
    person: Person,
) -> tuple[HealthRecord, Person, HealthRecordType]:
    """Načti uzamčený skrytý cíl a jeho autorizační kontext."""

    if (
        not isinstance(health_record, HealthRecord)
        or health_record.pk is None
        or not isinstance(person, Person)
        or person.pk is None
    ):
        raise HealthRecord.DoesNotExist
    try:
        candidate = (
            HealthRecord.objects.select_for_update()
            .select_related("person", "record_type")
            .get(pk=health_record.pk, person_id=person.pk)
        )
        current_person = Person.objects.select_for_update().get(pk=person.pk)
        current_type = HealthRecordType.objects.select_for_update().get(
            pk=candidate.record_type_id
        )
    except (
        HealthRecord.DoesNotExist,
        HealthRecordType.DoesNotExist,
        Person.DoesNotExist,
    ):
        raise HealthRecord.DoesNotExist from None
    return candidate, current_person, current_type


def _preauthorize_lifecycle_person(
    *,
    person: Person,
    actor: AbstractBaseUser,
) -> None:
    """Ověř kontext osoby před načtením skrytého zdravotního cíle."""

    if not isinstance(person, Person) or person.pk is None:
        raise HealthRecord.DoesNotExist
    try:
        current_person = Person.objects.get(pk=person.pk)
        person_visible = can_view_access_level(
            actor=actor,
            access_level=current_person.access_level,
        )
    except (Person.DoesNotExist, ValidationError):
        raise HealthRecord.DoesNotExist from None
    if (
        current_person.archived_at is not None
        or current_person.deleted_at is not None
        or not person_visible
    ):
        raise HealthRecord.DoesNotExist


def _authorize_lifecycle_context(
    *,
    candidate: HealthRecord,
    person: Person,
    record_type: HealthRecordType,
    actor: AbstractBaseUser,
) -> None:
    """Uplatni fail-closed content policy na uzamčený lifecycle cíl."""

    try:
        person_visible = can_view_access_level(
            actor=actor,
            access_level=person.access_level,
        )
        record_visible = can_view_health_record_access(
            actor=actor,
            access_level=candidate.access_level,
        )
    except ValidationError:
        raise HealthRecord.DoesNotExist from None

    if (
        person.archived_at is not None
        or person.deleted_at is not None
        or not person_visible
        or not record_visible
        or not record_type.is_active
    ):
        raise HealthRecord.DoesNotExist


def _authorize_lifecycle_target(
    *,
    candidate: HealthRecord,
    person: Person,
    record_type: HealthRecordType,
    actor: AbstractBaseUser,
) -> None:
    """Autorizuj cíl ACP-010, který nesmí být měkce odstraněný."""

    _authorize_lifecycle_context(
        candidate=candidate,
        person=person,
        record_type=record_type,
        actor=actor,
    )
    if candidate.deleted_at is not None:
        raise HealthRecord.DoesNotExist


def _reject_combined_lifecycle(candidate: HealthRecord) -> None:
    if candidate.archived_at is not None and candidate.deleted_at is not None:
        _raise_error(
            "health_record",
            "Zdravotní záznam má neplatnou kombinaci lifecycle stavů.",
            "health_record_lifecycle_invalid",
        )


def archive_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
    reason: str = "",
) -> HealthRecord:
    """Atomicky archivuj aktivní, actorovi dostupný zdravotní záznam."""

    with transaction.atomic():
        initial_actor = require_active_actor_permission(
            actor=actor,
            permission="health.change_healthrecord",
            denial_message=(
                "K archivaci zdravotního záznamu nemáte oprávnění."
            ),
        )
        _preauthorize_lifecycle_person(
            person=person,
            actor=initial_actor,
        )
        candidate, current_person, current_type = _load_lifecycle_target(
            health_record=health_record,
            person=person,
        )
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.change_healthrecord",
            denial_message=(
                "K archivaci zdravotního záznamu nemáte oprávnění."
            ),
        )
        _authorize_lifecycle_target(
            candidate=candidate,
            person=current_person,
            record_type=current_type,
            actor=current_actor,
        )
        if candidate.archived_at is not None:
            _raise_error(
                "health_record",
                "Archivovat lze pouze aktivní zdravotní záznam.",
                "health_record_not_active",
            )

        candidate.archived_at = timezone.now()
        candidate.archived_by = current_actor
        candidate.archive_reason = reason.strip()
        candidate.save(
            update_fields=(
                "archived_at",
                "archived_by",
                "archive_reason",
                "updated_at",
            )
        )
        return _reload(candidate.pk)


def restore_archived_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Atomicky obnov archivovaný, actorovi dostupný zdravotní záznam."""

    with transaction.atomic():
        initial_actor = require_active_actor_permission(
            actor=actor,
            permission="health.change_healthrecord",
            denial_message=(
                "K obnovení zdravotního záznamu nemáte oprávnění."
            ),
        )
        _preauthorize_lifecycle_person(
            person=person,
            actor=initial_actor,
        )
        candidate, current_person, current_type = _load_lifecycle_target(
            health_record=health_record,
            person=person,
        )
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.change_healthrecord",
            denial_message=(
                "K obnovení zdravotního záznamu nemáte oprávnění."
            ),
        )
        _authorize_lifecycle_target(
            candidate=candidate,
            person=current_person,
            record_type=current_type,
            actor=current_actor,
        )
        if candidate.archived_at is None:
            _raise_error(
                "health_record",
                "Obnovit lze pouze archivovaný zdravotní záznam.",
                "health_record_not_archived",
            )

        candidate.archived_at = None
        candidate.archived_by = None
        candidate.archive_reason = ""
        candidate.save(
            update_fields=(
                "archived_at",
                "archived_by",
                "archive_reason",
                "updated_at",
            )
        )
        return _reload(candidate.pk)


def soft_delete_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
    reason: str,
) -> HealthRecord:
    """Atomicky měkce odstraň aktivní, actorovi dostupný zdravotní záznam."""

    with transaction.atomic():
        initial_actor = require_active_actor_permission(
            actor=actor,
            permission="health.delete_healthrecord",
            denial_message=(
                "K odstranění zdravotního záznamu nemáte oprávnění."
            ),
        )
        _preauthorize_lifecycle_person(
            person=person,
            actor=initial_actor,
        )
        candidate, current_person, current_type = _load_lifecycle_target(
            health_record=health_record,
            person=person,
        )
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.delete_healthrecord",
            denial_message=(
                "K odstranění zdravotního záznamu nemáte oprávnění."
            ),
        )
        _authorize_lifecycle_context(
            candidate=candidate,
            person=current_person,
            record_type=current_type,
            actor=current_actor,
        )
        _reject_combined_lifecycle(candidate)
        if candidate.archived_at is not None or candidate.deleted_at is not None:
            _raise_error(
                "health_record",
                "Měkce odstranit lze pouze aktivní zdravotní záznam.",
                "health_record_not_active",
            )
        normalized_reason = reason.strip()
        if not normalized_reason:
            _raise_error(
                "deletion_reason",
                "Důvod odstranění zdravotního záznamu je povinný.",
                "health_record_deletion_reason_required",
            )

        candidate.deleted_at = timezone.now()
        candidate.deleted_by = current_actor
        candidate.deletion_reason = normalized_reason
        candidate.save(
            update_fields=(
                "deleted_at",
                "deleted_by",
                "deletion_reason",
                "updated_at",
            )
        )
        return _reload(candidate.pk)


def restore_soft_deleted_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Atomicky obnov měkce odstraněný, actorovi dostupný zdravotní záznam."""

    with transaction.atomic():
        initial_actor = require_active_actor_permission(
            actor=actor,
            permission="health.delete_healthrecord",
            denial_message=(
                "K obnovení odstraněného zdravotního záznamu nemáte oprávnění."
            ),
        )
        _preauthorize_lifecycle_person(
            person=person,
            actor=initial_actor,
        )
        candidate, current_person, current_type = _load_lifecycle_target(
            health_record=health_record,
            person=person,
        )
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.delete_healthrecord",
            denial_message=(
                "K obnovení odstraněného zdravotního záznamu nemáte oprávnění."
            ),
        )
        _authorize_lifecycle_context(
            candidate=candidate,
            person=current_person,
            record_type=current_type,
            actor=current_actor,
        )
        _reject_combined_lifecycle(candidate)
        if candidate.deleted_at is None or candidate.archived_at is not None:
            _raise_error(
                "health_record",
                "Obnovit lze pouze měkce odstraněný zdravotní záznam.",
                "health_record_not_soft_deleted",
            )

        candidate.deleted_at = None
        candidate.deleted_by = None
        candidate.deletion_reason = ""
        candidate.save(
            update_fields=(
                "deleted_at",
                "deleted_by",
                "deletion_reason",
                "updated_at",
            )
        )
        return _reload(candidate.pk)


def create_health_record(
    *,
    data: HealthRecordInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Atomicky vytvoř a vrať čerstvě načtený zdravotní záznam."""

    with transaction.atomic():
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.add_healthrecord",
            denial_message=(
                "K zápisu zdravotního záznamu nemáte oprávnění."
            ),
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
        current_actor = require_active_actor_permission(
            actor=actor,
            permission="health.change_healthrecord",
            denial_message=(
                "K zápisu zdravotního záznamu nemáte oprávnění."
            ),
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
