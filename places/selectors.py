"""Čtecí doménové dotazy aplikace places."""

from django.core.exceptions import ValidationError
from django.db.models import QuerySet

from people.models import Person

from .models import Residence

__all__ = ("get_person_residences",)


def get_person_residences(
    *,
    person: Person,
) -> QuerySet[Residence]:
    """Vrať úplnou permissionless historii bydlišť jedné osoby."""

    if person.pk is None or not Person.objects.filter(pk=person.pk).exists():
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být uložená a existovat v databázi.",
                    code="person_unsaved",
                )
            }
        )

    return (
        Residence.objects.filter(
            person_id=person.pk,
            deleted_at__isnull=True,
        )
        .select_related(
            "person",
            "residence_type",
            "place",
            "created_by",
        )
        .order_by(
            "sort_date",
            "sort_date_end",
            "residence_type__sort_order",
            "residence_type__name",
            "pk",
        )
    )
