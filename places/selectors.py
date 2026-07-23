"""Čtecí doménové dotazy aplikace places."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import QuerySet

from common.choices import AccessLevel
from common.permissions import can_view_access_level
from people.models import Person

from .models import GraveSite, Residence

__all__ = (
    "get_grave_sites",
    "get_person_residences",
    "get_visible_person_residences",
)

_ACCESS_LEVELS = (
    AccessLevel.PUBLIC,
    AccessLevel.AUTHENTICATED,
    AccessLevel.RESTRICTED,
    AccessLevel.ADMIN_ONLY,
)
_VIEW_ARCHIVED_PERSON_PERMISSION = "people.view_archived_person"
_VIEW_DELETED_PERSON_PERMISSION = "people.view_deleted_person"


def _person_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "person": ValidationError(
                "Osoba musí být uložená a existovat v databázi.",
                code="person_unsaved",
            )
        }
    )


def _load_current_person(person: Person) -> Person:
    if person.pk is None:
        raise _person_unsaved_error()

    try:
        return Person.objects.get(pk=person.pk)
    except Person.DoesNotExist as error:
        raise _person_unsaved_error() from error


def _get_lifecycle_permissions(
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[bool, bool]:
    if not actor.is_authenticated:
        return False, False

    current_actor = get_user_model()._default_manager.get(pk=actor.pk)
    if not current_actor.is_active:
        return False, False
    if current_actor.is_superuser:
        return True, True

    return (
        current_actor.has_perm(_VIEW_ARCHIVED_PERSON_PERMISSION),
        current_actor.has_perm(_VIEW_DELETED_PERSON_PERMISSION),
    )


def _is_person_visible(
    person: Person,
    *,
    access_visibility: dict[str, bool],
    can_view_archived: bool,
    can_view_deleted: bool,
) -> bool:
    return (
        access_visibility[person.access_level]
        and (person.archived_at is None or can_view_archived)
        and (person.deleted_at is None or can_view_deleted)
    )


def get_grave_sites() -> QuerySet[GraveSite]:
    """Vrať úplný permissionless katalog nesmazaných hrobových míst."""

    return GraveSite.objects.filter(
        deleted_at__isnull=True,
    ).select_related(
        "grave_site_type",
        "place",
        "created_by",
    )


def get_person_residences(
    *,
    person: Person,
) -> QuerySet[Residence]:
    """Vrať úplnou permissionless historii bydlišť jedné osoby."""

    if person.pk is None or not Person.objects.filter(pk=person.pk).exists():
        raise _person_unsaved_error()

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


def get_visible_person_residences(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[Residence]:
    """Vrať historii bydlišť osoby viditelnou pro aktuálního actora."""

    access_visibility = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    can_view_archived, can_view_deleted = _get_lifecycle_permissions(actor)
    current_person = _load_current_person(person)

    if not _is_person_visible(
        current_person,
        access_visibility=access_visibility,
        can_view_archived=can_view_archived,
        can_view_deleted=can_view_deleted,
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit tuto osobu.")

    visible_access_levels = tuple(
        access_level
        for access_level, is_visible in access_visibility.items()
        if is_visible
    )
    return get_person_residences(person=current_person).filter(
        access_level__in=visible_access_levels,
    )
