"""Čtecí doménové dotazy aplikace materials."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, QuerySet

from common.choices import AccessLevel
from common.permissions import can_view_access_level
from people.models import Person

from .choices import FileStatus
from .models import PersonAttachment

__all__ = (
    "get_person_attachment_links",
    "get_visible_person_attachment_links",
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
    if not isinstance(person, Person) or person.pk is None:
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


def _person_lifecycle_filter(
    *,
    can_view_archived: bool,
    can_view_deleted: bool,
) -> Q:
    condition = Q()
    if not can_view_archived:
        condition &= Q(person__archived_at__isnull=True)
    if not can_view_deleted:
        condition &= Q(person__deleted_at__isnull=True)
    return condition


def get_person_attachment_links(
    *,
    person: Person,
) -> QuerySet[PersonAttachment]:
    """Vrať permissionless historii nesmazaných vazeb příloh osoby."""

    current_person = _load_current_person(person)
    return PersonAttachment.objects.filter(
        person_id=current_person.pk,
        deleted_at__isnull=True,
    ).select_related(
        "person",
        "attachment",
        "attachment__category",
        "attachment__created_by",
        "role",
        "created_by",
    )


def get_visible_person_attachment_links(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[PersonAttachment]:
    """Vrať dostupné přílohy osoby viditelné pro aktuálního actora."""

    access_visibility = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    can_view_archived, can_view_deleted = _get_lifecycle_permissions(actor)
    current_person = _load_current_person(person)
    if not (
        access_visibility.get(current_person.access_level, False)
        and (current_person.archived_at is None or can_view_archived)
        and (current_person.deleted_at is None or can_view_deleted)
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit tuto osobu.")

    visible_access_levels = tuple(
        access_level
        for access_level, is_visible in access_visibility.items()
        if is_visible
    )
    return get_person_attachment_links(person=current_person).filter(
        _person_lifecycle_filter(
            can_view_archived=can_view_archived,
            can_view_deleted=can_view_deleted,
        ),
        access_level__in=visible_access_levels,
        archived_at__isnull=True,
        person__access_level__in=visible_access_levels,
        attachment__access_level__in=visible_access_levels,
        attachment__archived_at__isnull=True,
        attachment__deleted_at__isnull=True,
        attachment__file_status=FileStatus.AVAILABLE,
    )
