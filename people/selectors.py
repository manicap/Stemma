"""Čtecí doménové dotazy aplikace people."""

from django.core.exceptions import ValidationError
from django.db.models import QuerySet, Subquery

from .models import Person, Relationship

__all__ = ("get_biological_siblings",)


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
