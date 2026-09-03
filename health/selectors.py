"""Actor-aware čtecí dotazy zdravotních záznamů."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from people.models import Person

from .models import HealthRecord
from .permissions import get_health_record_visibility_filter

__all__ = (
    "get_visible_health_record",
    "get_visible_health_records",
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
