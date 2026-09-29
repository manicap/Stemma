"""Actor-aware čtecí dotazy zdravotních záznamů."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from common.permissions import (
    can_view_access_level,
    require_active_actor_permission,
)
from people.models import Person

from .models import HealthRecord
from .permissions import (
    get_archived_health_record_management_filter,
    get_health_record_visibility_filter,
)

__all__ = (
    "get_archived_health_record_for_management",
    "get_visible_health_record",
    "get_visible_health_records",
    "list_archived_health_records_for_management",
)


def _visible_health_records(
    *,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    return (
        HealthRecord.objects.filter(
            get_health_record_visibility_filter(actor=actor)
        )
        .select_related("person", "record_type", "place", "created_by")
        .order_by("sort_date", "sort_date_end", "record_type__sort_order", "pk")
    )


def get_visible_health_records(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    """Vrať aktivní zdravotní záznamy jedné dostupné aktivní osoby."""

    person_id = getattr(person, "pk", None)
    if (
        not isinstance(person, Person)
        or person_id is None
        or not Person.objects.filter(pk=person_id).exists()
    ):
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být uložená a existovat v databázi.",
                    code="person_unsaved",
                )
            }
        )
    return _visible_health_records(actor=actor).filter(person_id=person_id)


def get_visible_health_record(
    *,
    health_record_id: int,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Vrať jeden viditelný aktivní záznam nebo jednotně selži."""

    if isinstance(health_record_id, bool) or not isinstance(
        health_record_id, int
    ):
        raise HealthRecord.DoesNotExist
    try:
        return _visible_health_records(actor=actor).get(pk=health_record_id)
    except (OverflowError, TypeError, ValueError) as error:
        raise HealthRecord.DoesNotExist from error


def _archived_health_records_for_management(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    current_actor = require_active_actor_permission(
        actor=actor,
        permission="health.change_healthrecord",
        denial_message=(
            "Ke správě archivu zdravotních záznamů nemáte oprávnění."
        ),
    )
    person_id = getattr(person, "pk", None)
    if not isinstance(person, Person) or person_id is None:
        raise Person.DoesNotExist
    try:
        current_person = Person.objects.get(pk=person_id)
        person_visible = can_view_access_level(
            actor=current_actor,
            access_level=current_person.access_level,
        )
    except (Person.DoesNotExist, ValidationError):
        raise Person.DoesNotExist from None
    if (
        current_person.archived_at is not None
        or current_person.deleted_at is not None
        or not person_visible
    ):
        raise Person.DoesNotExist
    return (
        HealthRecord.objects.filter(
            get_archived_health_record_management_filter(
                actor=current_actor,
            ),
            person_id=current_person.pk,
        )
        .select_related("person", "record_type", "place", "created_by")
        .order_by("sort_date", "sort_date_end", "record_type__sort_order", "pk")
    )


def list_archived_health_records_for_management(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    """Vrať spravovatelné archivované záznamy jedné aktivní osoby."""

    return _archived_health_records_for_management(
        person=person,
        actor=actor,
    )


def get_archived_health_record_for_management(
    *,
    health_record_id: int,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Vrať archivovaný cíl obnovy přes fail-closed management hranici."""

    if isinstance(health_record_id, bool) or not isinstance(
        health_record_id, int
    ):
        raise HealthRecord.DoesNotExist
    try:
        return _archived_health_records_for_management(
            person=person,
            actor=actor,
        ).get(pk=health_record_id)
    except (OverflowError, TypeError, ValueError) as error:
        raise HealthRecord.DoesNotExist from error
