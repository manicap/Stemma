"""Transportně neutrální aplikační čtení zdravotních záznamů."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet

from people.models import Person

from .models import HealthRecord
from .selectors import get_visible_health_record, get_visible_health_records

__all__ = (
    "get_health_record_detail",
    "list_health_records",
)


def list_health_records(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    """Vrať actorovi dostupné zdravotní záznamy konkrétní osoby."""

    return get_visible_health_records(person=person, actor=actor)


def get_health_record_detail(
    *,
    health_record_id: int,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Vrať actorovi dostupný detail se sjednoceným bezpečným selháním."""

    return get_visible_health_record(
        health_record_id=health_record_id,
        actor=actor,
    )
