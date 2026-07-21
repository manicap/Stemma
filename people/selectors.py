"""Čtecí doménové dotazy aplikace people."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet, Subquery

from .models import Person, Relationship

__all__ = (
    "SiblingOverviewItem",
    "get_biological_siblings",
    "get_sibling_overview",
)

_SIBLING_REASON_ORDER = (
    "biological",
    "sibling",
    "adoptive_sibling",
    "step_sibling",
    "social_sibling",
)
_EXPLICIT_SIBLING_CODES = _SIBLING_REASON_ORDER[1:]


@dataclass(frozen=True, slots=True)
class SiblingOverviewItem:
    """Osoba a všechny důvody její sourozenecké vazby."""

    person: Person
    relationship_codes: tuple[str, ...]


def get_biological_siblings(
    *,
    person: Person,
) -> QuerySet[Person]:
    """Vrať biologické sourozence odvozené ze společného rodiče."""

    if person.pk is None or not Person.objects.filter(pk=person.pk).exists():
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být před vyhledáním sourozenců uložena.",
                    code="person_unsaved",
                )
            }
        )

    biological_parent_ids = Relationship.objects.filter(
        deleted_at__isnull=True,
        relationship_type__code="biological_parent",
        person_b_id=person.pk,
    ).values("person_a_id")
    biological_sibling_ids = Relationship.objects.filter(
        deleted_at__isnull=True,
        relationship_type__code="biological_parent",
        person_a_id__in=Subquery(biological_parent_ids),
    ).values("person_b_id")

    return (
        Person.objects.filter(
            deleted_at__isnull=True,
            pk__in=Subquery(biological_sibling_ids),
        )
        .exclude(pk=person.pk)
        .distinct()
    )


def get_sibling_overview(
    *,
    person: Person,
) -> tuple[SiblingOverviewItem, ...]:
    """Vrať agregovaný přehled biologických a explicitních sourozenců."""

    people_by_id: dict[int, Person] = {}
    reasons_by_person_id: dict[int, set[str]] = {}

    for sibling in get_biological_siblings(person=person):
        people_by_id[sibling.pk] = sibling
        reasons_by_person_id.setdefault(sibling.pk, set()).add(
            "biological"
        )

    explicit_relationships = Relationship.objects.filter(
        Q(person_a=person) | Q(person_b=person),
        deleted_at__isnull=True,
        relationship_type__code__in=_EXPLICIT_SIBLING_CODES,
    ).select_related(
        "relationship_type",
        "person_a",
        "person_b",
    )
    for relationship in explicit_relationships:
        sibling = (
            relationship.person_b
            if relationship.person_a_id == person.pk
            else relationship.person_a
        )
        if sibling.pk == person.pk or sibling.deleted_at is not None:
            continue

        people_by_id[sibling.pk] = sibling
        reasons_by_person_id.setdefault(sibling.pk, set()).add(
            relationship.relationship_type.code
        )

    items = (
        SiblingOverviewItem(
            person=sibling,
            relationship_codes=tuple(
                reason
                for reason in _SIBLING_REASON_ORDER
                if reason in reasons_by_person_id[sibling_id]
            ),
        )
        for sibling_id, sibling in people_by_id.items()
    )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.person.last_name,
                item.person.first_name,
                item.person.pk,
            ),
        )
    )
