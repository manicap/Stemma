"""Actor-aware read selectors for events."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, CharField, F, QuerySet, Value, When

from common.choices import AccessLevel
from common.permissions import can_view_access_level
from people.models import Person
from people.selectors import get_visible_person

from .models import Event

__all__ = ("get_visible_person_events",)


def _load_visible_person(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> Person:
    if getattr(person, "pk", None) is None:
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být uložená v databázi.",
                    code="person_unsaved",
                )
            }
        )
    try:
        return get_visible_person(person_id=person.pk, actor=actor)
    except Person.DoesNotExist as error:
        raise PermissionDenied(
            "Nemáte oprávnění zobrazit tuto osobu."
        ) from error


def get_visible_person_events(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[Event]:
    """Return active events visible through one visible person's participation."""

    current_person = _load_visible_person(person=person, actor=actor)
    visible_levels = tuple(
        level
        for level in AccessLevel.values
        if can_view_access_level(actor=actor, access_level=level)
    )
    return (
        Event.objects.filter(
            participants__person=current_person,
            access_level__in=visible_levels,
            archived_at__isnull=True,
            deleted_at__isnull=True,
        )
        .select_related("event_type")
        .annotate(
            presentation_place_name=Case(
                When(
                    place__access_level__in=visible_levels,
                    place__archived_at__isnull=True,
                    place__deleted_at__isnull=True,
                    then=F("place__name"),
                ),
                default=Value(None),
                output_field=CharField(),
            )
        )
        .distinct()
    )
