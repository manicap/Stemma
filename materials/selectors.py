"""Čtecí doménové dotazy aplikace materials."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, QuerySet

from common.choices import AccessLevel
from common.permissions import can_view_access_level
from events.models import Event
from people.models import Person, PersonName, Relationship

from .choices import FileStatus
from .models import (
    EventAttachment,
    EventSource,
    PersonAttachment,
    PersonNameSource,
    RelationshipSource,
)

__all__ = (
    "get_event_attachment_links",
    "get_event_source_links",
    "get_person_attachment_links",
    "get_person_name_source_links",
    "get_relationship_source_links",
    "get_visible_event_attachment_links",
    "get_visible_event_source_links",
    "get_visible_person_attachment_links",
    "get_visible_person_name_source_links",
    "get_visible_relationship_source_links",
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


def _event_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "event": ValidationError(
                "Událost musí být uložená a existovat v databázi.",
                code="event_unsaved",
            )
        }
    )


def _person_name_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "person_name": ValidationError(
                "Jméno osoby musí být uložené a existovat v databázi.",
                code="person_name_unsaved",
            )
        }
    )


def _relationship_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "relationship": ValidationError(
                "Vazba musí být uložená a existovat v databázi.",
                code="relationship_unsaved",
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


def _load_current_event(event: Event) -> Event:
    if not isinstance(event, Event) or event.pk is None:
        raise _event_unsaved_error()

    try:
        return Event.objects.get(pk=event.pk)
    except Event.DoesNotExist as error:
        raise _event_unsaved_error() from error


def _load_current_person_name(person_name: PersonName) -> PersonName:
    if not isinstance(person_name, PersonName) or person_name.pk is None:
        raise _person_name_unsaved_error()

    try:
        return PersonName.objects.select_related("person").get(
            pk=person_name.pk
        )
    except PersonName.DoesNotExist as error:
        raise _person_name_unsaved_error() from error


def _load_current_relationship(relationship: Relationship) -> Relationship:
    if not isinstance(relationship, Relationship) or relationship.pk is None:
        raise _relationship_unsaved_error()

    try:
        return Relationship.objects.select_related(
            "person_a",
            "person_b",
        ).get(pk=relationship.pk)
    except Relationship.DoesNotExist as error:
        raise _relationship_unsaved_error() from error


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


def _person_name_parent_lifecycle_filter(
    *,
    can_view_archived: bool,
    can_view_deleted: bool,
) -> Q:
    condition = Q()
    if not can_view_archived:
        condition &= Q(person_name__person__archived_at__isnull=True)
    if not can_view_deleted:
        condition &= Q(person_name__person__deleted_at__isnull=True)
    return condition


def _relationship_people_lifecycle_filter(
    *,
    can_view_archived: bool,
) -> Q:
    condition = Q(
        relationship__person_a__deleted_at__isnull=True,
        relationship__person_b__deleted_at__isnull=True,
    )
    if not can_view_archived:
        condition &= Q(
            relationship__person_a__archived_at__isnull=True,
            relationship__person_b__archived_at__isnull=True,
        )
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


def get_event_attachment_links(
    *,
    event: Event,
) -> QuerySet[EventAttachment]:
    """Vrať permissionless historii nesmazaných vazeb příloh události."""

    current_event = _load_current_event(event)
    return EventAttachment.objects.filter(
        event_id=current_event.pk,
        deleted_at__isnull=True,
    ).select_related(
        "event",
        "event__event_type",
        "event__place",
        "event__created_by",
        "attachment",
        "attachment__category",
        "attachment__created_by",
        "role",
        "created_by",
    )


def get_person_name_source_links(
    *,
    person_name: PersonName,
) -> QuerySet[PersonNameSource]:
    """Vrať permissionless historii nesmazaných vazeb zdrojů jména."""

    current_name = _load_current_person_name(person_name)
    return PersonNameSource.objects.filter(
        person_name_id=current_name.pk,
        deleted_at__isnull=True,
    ).select_related(
        "person_name",
        "person_name__person",
        "person_name__name_type",
        "person_name__created_by",
        "source",
        "source__source_type",
        "source__created_by",
        "role",
        "created_by",
    )


def get_event_source_links(
    *,
    event: Event,
) -> QuerySet[EventSource]:
    """Vrať permissionless historii nesmazaných vazeb zdrojů události."""

    current_event = _load_current_event(event)
    return EventSource.objects.filter(
        event_id=current_event.pk,
        deleted_at__isnull=True,
    ).select_related(
        "event",
        "event__event_type",
        "event__place",
        "event__created_by",
        "source",
        "source__source_type",
        "source__created_by",
        "role",
        "created_by",
    )


def get_relationship_source_links(
    *,
    relationship: Relationship,
) -> QuerySet[RelationshipSource]:
    """Vrať permissionless historii nesmazaných zdrojů konkrétní vazby."""

    current = _load_current_relationship(relationship)
    return RelationshipSource.objects.filter(
        relationship_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "relationship",
        "relationship__relationship_type",
        "relationship__person_a",
        "relationship__person_b",
        "relationship__created_by",
        "source",
        "source__source_type",
        "source__created_by",
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


def get_visible_event_attachment_links(
    *,
    event: Event,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[EventAttachment]:
    """Vrať dostupné přílohy události viditelné pro aktuálního actora."""

    access_visibility = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    current_event = _load_current_event(event)
    if not (
        access_visibility.get(current_event.access_level, False)
        and current_event.archived_at is None
        and current_event.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit tuto událost.")

    visible_access_levels = tuple(
        access_level
        for access_level, is_visible in access_visibility.items()
        if is_visible
    )
    return get_event_attachment_links(event=current_event).filter(
        access_level__in=visible_access_levels,
        archived_at__isnull=True,
        event__access_level__in=visible_access_levels,
        event__archived_at__isnull=True,
        event__deleted_at__isnull=True,
        attachment__access_level__in=visible_access_levels,
        attachment__archived_at__isnull=True,
        attachment__deleted_at__isnull=True,
        attachment__file_status=FileStatus.AVAILABLE,
    )


def get_visible_person_name_source_links(
    *,
    person_name: PersonName,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[PersonNameSource]:
    """Vrať zdroje konkrétního jména viditelné po celé jeho cestě."""

    access_visibility = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    can_view_archived, can_view_deleted = _get_lifecycle_permissions(actor)
    current_name = _load_current_person_name(person_name)
    person = current_name.person
    if not (
        access_visibility.get(person.access_level, False)
        and (person.archived_at is None or can_view_archived)
        and (person.deleted_at is None or can_view_deleted)
        and access_visibility.get(current_name.access_level, False)
        and current_name.archived_at is None
        and current_name.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit toto jméno osoby.")

    visible_access_levels = tuple(
        access_level
        for access_level, is_visible in access_visibility.items()
        if is_visible
    )
    return get_person_name_source_links(person_name=current_name).filter(
        _person_name_parent_lifecycle_filter(
            can_view_archived=can_view_archived,
            can_view_deleted=can_view_deleted,
        ),
        access_level__in=visible_access_levels,
        archived_at__isnull=True,
        person_name__access_level__in=visible_access_levels,
        person_name__archived_at__isnull=True,
        person_name__deleted_at__isnull=True,
        person_name__person__access_level__in=visible_access_levels,
        source__access_level__in=visible_access_levels,
        source__archived_at__isnull=True,
        source__deleted_at__isnull=True,
    )


def get_visible_event_source_links(
    *,
    event: Event,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[EventSource]:
    """Vrať zdroje konkrétní události viditelné po celé její cestě."""

    access_visibility = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    current_event = _load_current_event(event)
    if not (
        access_visibility.get(current_event.access_level, False)
        and current_event.archived_at is None
        and current_event.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit tuto událost.")

    visible_access_levels = tuple(
        access_level
        for access_level, is_visible in access_visibility.items()
        if is_visible
    )
    return get_event_source_links(event=current_event).filter(
        access_level__in=visible_access_levels,
        archived_at__isnull=True,
        event__access_level__in=visible_access_levels,
        event__archived_at__isnull=True,
        event__deleted_at__isnull=True,
        source__access_level__in=visible_access_levels,
        source__archived_at__isnull=True,
        source__deleted_at__isnull=True,
    )


def get_visible_relationship_source_links(
    *,
    relationship: Relationship,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[RelationshipSource]:
    """Vrať zdroje vazby viditelné přes vazbu i obě propojené osoby."""

    visibility = {
        level: can_view_access_level(actor=actor, access_level=level)
        for level in _ACCESS_LEVELS
    }
    can_view_archived, _ = _get_lifecycle_permissions(actor)
    current = _load_current_relationship(relationship)
    people = (current.person_a, current.person_b)
    if not (
        visibility.get(current.access_level, False)
        and current.deleted_at is None
        and all(
            visibility.get(person.access_level, False)
            and (person.archived_at is None or can_view_archived)
            and person.deleted_at is None
            for person in people
        )
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit tuto vazbu.")

    visible_levels = tuple(
        level for level, is_visible in visibility.items() if is_visible
    )
    return get_relationship_source_links(relationship=current).filter(
        _relationship_people_lifecycle_filter(
            can_view_archived=can_view_archived,
        ),
        access_level__in=visible_levels,
        archived_at__isnull=True,
        relationship__access_level__in=visible_levels,
        relationship__deleted_at__isnull=True,
        relationship__person_a__access_level__in=visible_levels,
        relationship__person_b__access_level__in=visible_levels,
        source__access_level__in=visible_levels,
        source__archived_at__isnull=True,
        source__deleted_at__isnull=True,
    )
