"""Čtecí doménové dotazy aplikace materials."""

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, QuerySet

from common.choices import AccessLevel
from common.permissions import can_view_access_level
from events.models import Event
from health.models import HealthRecord
from health.permissions import get_health_record_visibility_filter
from people.models import Person, PersonName, Relationship
from places.models import GraveSite, Residence

from .access_policy import (
    can_access_private_attachment,
    get_attachment_privacy_filter,
)
from .choices import AttachmentPrivacyStatus, FileStatus
from .models import (
    Attachment,
    AttachmentLinkModel,
    EventAttachment,
    EventSource,
    GraveSiteAttachment,
    GraveSiteSource,
    HealthRecordAttachment,
    HealthRecordSource,
    PersonAttachment,
    PersonNameSource,
    ResidenceAttachment,
    ResidenceSource,
    RelationshipAttachment,
    RelationshipSource,
)

__all__ = (
    "get_event_attachment_links",
    "get_event_source_links",
    "get_grave_site_attachment_links",
    "get_grave_site_source_links",
    "get_person_attachment_links",
    "get_person_name_source_links",
    "get_residence_attachment_links",
    "get_residence_source_links",
    "get_relationship_attachment_links",
    "get_relationship_source_links",
    "get_visible_event_attachment_links",
    "get_visible_event_source_links",
    "get_visible_grave_site_attachment_links",
    "get_visible_grave_site_source_links",
    "get_visible_health_record_attachment_links",
    "get_visible_health_record_source_links",
    "get_visible_person_attachment_links",
    "get_visible_person_name_source_links",
    "get_visible_residence_attachment_links",
    "get_visible_residence_source_links",
    "get_visible_relationship_attachment_links",
    "get_visible_relationship_source_links",
    "get_attachment_link_presentation",
    "AttachmentMetadataPresentation",
    "PrivateAttachmentPlaceholder",
)

_ACCESS_LEVELS = (
    AccessLevel.PUBLIC,
    AccessLevel.AUTHENTICATED,
    AccessLevel.RESTRICTED,
    AccessLevel.ADMIN_ONLY,
)
_VIEW_ARCHIVED_PERSON_PERMISSION = "people.view_archived_person"
_VIEW_DELETED_PERSON_PERMISSION = "people.view_deleted_person"


def _attachment_privacy_filter(
    actor: AbstractBaseUser | AnonymousUser,
) -> Q:
    return get_attachment_privacy_filter(actor=actor)


@dataclass(frozen=True, slots=True)
class AttachmentMetadataPresentation:
    """Bezpečná běžná prezentace metadat bez interního storage klíče."""

    attachment_id: int
    label: str
    display_name: str
    description: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    file_status: str
    privacy_status: str
    access_level: str
    creator_name: str
    provenance: str
    original_owner: str
    language: str
    technical_metadata: Mapping[str, object]
    created_by_id: int | None

    @property
    def is_redacted(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class PrivateAttachmentPlaceholder:
    """Minimální redigovaná prezentace bez reference na ORM objekt."""

    label: str = "Soukromý dokument"

    @property
    def is_redacted(self) -> bool:
        return True


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


def _residence_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "residence": ValidationError(
                "Bydliště musí být uložené a existovat v databázi.",
                code="residence_unsaved",
            )
        }
    )


def _grave_site_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "grave_site": ValidationError(
                "Hrobové místo musí být uložené a existovat v databázi.",
                code="grave_site_unsaved",
            )
        }
    )


def _health_record_unsaved_error() -> ValidationError:
    return ValidationError(
        {
            "health_record": ValidationError(
                "Zdravotní záznam musí být uložený a existovat v databázi.",
                code="health_record_unsaved",
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


def _load_current_residence(residence: Residence) -> Residence:
    if not isinstance(residence, Residence) or residence.pk is None:
        raise _residence_unsaved_error()

    try:
        return Residence.objects.select_related("person").get(pk=residence.pk)
    except Residence.DoesNotExist as error:
        raise _residence_unsaved_error() from error


def _load_current_grave_site(grave_site: GraveSite) -> GraveSite:
    if not isinstance(grave_site, GraveSite) or grave_site.pk is None:
        raise _grave_site_unsaved_error()

    try:
        return GraveSite.objects.get(pk=grave_site.pk)
    except GraveSite.DoesNotExist as error:
        raise _grave_site_unsaved_error() from error


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


def _residence_person_lifecycle_filter(
    *,
    can_view_archived: bool,
    can_view_deleted: bool,
) -> Q:
    condition = Q()
    if not can_view_archived:
        condition &= Q(residence__person__archived_at__isnull=True)
    if not can_view_deleted:
        condition &= Q(residence__person__deleted_at__isnull=True)
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


def get_relationship_attachment_links(
    *,
    relationship: Relationship,
) -> QuerySet[RelationshipAttachment]:
    """Vrať permissionless historii nesmazaných příloh konkrétní vazby."""

    current = _load_current_relationship(relationship)
    return RelationshipAttachment.objects.filter(
        relationship_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "relationship",
        "relationship__relationship_type",
        "relationship__person_a",
        "relationship__person_b",
        "relationship__created_by",
        "attachment",
        "attachment__category",
        "attachment__created_by",
        "role",
        "created_by",
    )


def get_residence_attachment_links(
    *,
    residence: Residence,
) -> QuerySet[ResidenceAttachment]:
    """Vrať permissionless historii nesmazaných příloh bydliště."""

    current = _load_current_residence(residence)
    return ResidenceAttachment.objects.filter(
        residence_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "residence",
        "residence__person",
        "residence__residence_type",
        "residence__place",
        "residence__created_by",
        "attachment",
        "attachment__category",
        "attachment__created_by",
        "role",
        "created_by",
    )


def get_residence_source_links(
    *,
    residence: Residence,
) -> QuerySet[ResidenceSource]:
    """Vrať permissionless historii nesmazaných zdrojů bydliště."""

    current = _load_current_residence(residence)
    return ResidenceSource.objects.filter(
        residence_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "residence",
        "residence__person",
        "residence__residence_type",
        "residence__place",
        "residence__created_by",
        "source",
        "source__source_type",
        "source__created_by",
        "role",
        "created_by",
    )


def get_grave_site_attachment_links(
    *,
    grave_site: GraveSite,
) -> QuerySet[GraveSiteAttachment]:
    """Vrať permissionless historii nesmazaných příloh hrobového místa."""

    current = _load_current_grave_site(grave_site)
    return GraveSiteAttachment.objects.filter(
        grave_site_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "grave_site",
        "grave_site__grave_site_type",
        "grave_site__place",
        "grave_site__created_by",
        "attachment",
        "attachment__category",
        "attachment__created_by",
        "role",
        "created_by",
    )


def get_grave_site_source_links(
    *,
    grave_site: GraveSite,
) -> QuerySet[GraveSiteSource]:
    """Vrať permissionless historii nesmazaných zdrojů hrobového místa."""

    current = _load_current_grave_site(grave_site)
    return GraveSiteSource.objects.filter(
        grave_site_id=current.pk,
        deleted_at__isnull=True,
    ).select_related(
        "grave_site",
        "grave_site__grave_site_type",
        "grave_site__place",
        "grave_site__created_by",
        "source",
        "source__source_type",
        "source__created_by",
        "role",
        "created_by",
    )


def _get_visible_person_attachment_links(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
    enforce_private_access: bool,
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
    queryset = get_person_attachment_links(person=current_person).filter(
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
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_person_attachment_links(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[PersonAttachment]:
    """Vrať plná metadata příloh osoby dostupná aktuálnímu actorovi."""

    return _get_visible_person_attachment_links(
        person=person,
        actor=actor,
        enforce_private_access=True,
    )


def _get_visible_event_attachment_links(
    *,
    event: Event,
    actor: AbstractBaseUser | AnonymousUser,
    enforce_private_access: bool,
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
    queryset = get_event_attachment_links(event=current_event).filter(
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
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_event_attachment_links(
    *,
    event: Event,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[EventAttachment]:
    """Vrať plná metadata příloh události dostupná aktuálnímu actorovi."""

    return _get_visible_event_attachment_links(
        event=event,
        actor=actor,
        enforce_private_access=True,
    )


def _visible_health_record_attachment_links(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    visible_health_records: QuerySet[HealthRecord] | None = None,
    enforce_private_access: bool = True,
) -> QuerySet[HealthRecordAttachment]:
    """Sestav jediný actor-aware queryset vydatelných health vazeb."""

    if visible_health_records is None:
        visible_health_records = HealthRecord.objects.filter(
            get_health_record_visibility_filter(actor=actor)
        )
    visible_levels = tuple(
        level
        for level in _ACCESS_LEVELS
        if can_view_access_level(actor=actor, access_level=level)
    )
    queryset = (
        HealthRecordAttachment.objects.filter(
            health_record_id__in=visible_health_records.values("pk"),
            access_level__in=visible_levels,
            archived_at__isnull=True,
            deleted_at__isnull=True,
            attachment__access_level__in=visible_levels,
            attachment__archived_at__isnull=True,
            attachment__deleted_at__isnull=True,
            attachment__file_status=FileStatus.AVAILABLE,
        )
        .select_related(
            "health_record",
            "health_record__person",
            "health_record__record_type",
            "health_record__place",
            "health_record__created_by",
            "attachment",
            "attachment__category",
            "attachment__created_by",
            "role",
            "created_by",
        )
    )
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_health_record_attachment_links(
    *,
    health_record: HealthRecord,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecordAttachment]:
    """Vrať vydatelné přílohy dostupného zdravotního záznamu."""

    if not isinstance(health_record, HealthRecord) or health_record.pk is None:
        raise _health_record_unsaved_error()

    if not HealthRecord.objects.filter(pk=health_record.pk).exists():
        raise _health_record_unsaved_error()

    visible_health_records = HealthRecord.objects.filter(
        get_health_record_visibility_filter(actor=actor)
    )
    current = visible_health_records.get(pk=health_record.pk)
    return _visible_health_record_attachment_links(
        actor=actor,
        visible_health_records=visible_health_records,
    ).filter(
        health_record_id=current.pk,
    )


def _visible_health_record_source_links(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    visible_health_records: QuerySet[HealthRecord] | None = None,
) -> QuerySet[HealthRecordSource]:
    """Sestav jediný actor-aware queryset dostupných health source vazeb."""

    if visible_health_records is None:
        visible_health_records = HealthRecord.objects.filter(
            get_health_record_visibility_filter(actor=actor)
        )
    visible_levels = tuple(
        level
        for level in _ACCESS_LEVELS
        if can_view_access_level(actor=actor, access_level=level)
    )
    return (
        HealthRecordSource.objects.filter(
            health_record_id__in=visible_health_records.values("pk"),
            access_level__in=visible_levels,
            archived_at__isnull=True,
            deleted_at__isnull=True,
            source__access_level__in=visible_levels,
            source__archived_at__isnull=True,
            source__deleted_at__isnull=True,
        )
        .select_related(
            "health_record",
            "health_record__person",
            "health_record__record_type",
            "health_record__place",
            "health_record__created_by",
            "source",
            "source__source_type",
            "source__created_by",
            "role",
            "created_by",
        )
    )


def get_visible_health_record_source_links(
    *,
    health_record: HealthRecord,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecordSource]:
    """Vrať dostupné zdroje viditelného zdravotního záznamu."""

    if not isinstance(health_record, HealthRecord) or health_record.pk is None:
        raise _health_record_unsaved_error()
    if not HealthRecord.objects.filter(pk=health_record.pk).exists():
        raise _health_record_unsaved_error()

    visible_health_records = HealthRecord.objects.filter(
        get_health_record_visibility_filter(actor=actor)
    )
    current = visible_health_records.get(pk=health_record.pk)
    return _visible_health_record_source_links(
        actor=actor,
        visible_health_records=visible_health_records,
    ).filter(health_record_id=current.pk)


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


def _get_visible_relationship_attachment_links(
    *,
    relationship: Relationship,
    actor: AbstractBaseUser | AnonymousUser,
    enforce_private_access: bool,
) -> QuerySet[RelationshipAttachment]:
    """Vrať dostupné přílohy viditelné přes vazbu i obě osoby."""

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
    queryset = get_relationship_attachment_links(relationship=current).filter(
        _relationship_people_lifecycle_filter(
            can_view_archived=can_view_archived,
        ),
        access_level__in=visible_levels,
        archived_at__isnull=True,
        relationship__access_level__in=visible_levels,
        relationship__deleted_at__isnull=True,
        relationship__person_a__access_level__in=visible_levels,
        relationship__person_b__access_level__in=visible_levels,
        attachment__access_level__in=visible_levels,
        attachment__archived_at__isnull=True,
        attachment__deleted_at__isnull=True,
        attachment__file_status=FileStatus.AVAILABLE,
    )
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_relationship_attachment_links(
    *,
    relationship: Relationship,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[RelationshipAttachment]:
    """Vrať plná metadata příloh vztahu dostupná aktuálnímu actorovi."""

    return _get_visible_relationship_attachment_links(
        relationship=relationship,
        actor=actor,
        enforce_private_access=True,
    )


def _get_visible_residence_attachment_links(
    *,
    residence: Residence,
    actor: AbstractBaseUser | AnonymousUser,
    enforce_private_access: bool,
) -> QuerySet[ResidenceAttachment]:
    """Vrať dostupné přílohy viditelné v kontextu bydliště a osoby."""

    visibility = {
        level: can_view_access_level(actor=actor, access_level=level)
        for level in _ACCESS_LEVELS
    }
    can_view_archived, can_view_deleted = _get_lifecycle_permissions(actor)
    current = _load_current_residence(residence)
    person = current.person
    if not (
        visibility.get(person.access_level, False)
        and (person.archived_at is None or can_view_archived)
        and (person.deleted_at is None or can_view_deleted)
        and visibility.get(current.access_level, False)
        and current.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit toto bydliště.")

    visible_levels = tuple(
        level for level, is_visible in visibility.items() if is_visible
    )
    queryset = get_residence_attachment_links(residence=current).filter(
        _residence_person_lifecycle_filter(
            can_view_archived=can_view_archived,
            can_view_deleted=can_view_deleted,
        ),
        access_level__in=visible_levels,
        archived_at__isnull=True,
        residence__access_level__in=visible_levels,
        residence__deleted_at__isnull=True,
        residence__person__access_level__in=visible_levels,
        attachment__access_level__in=visible_levels,
        attachment__archived_at__isnull=True,
        attachment__deleted_at__isnull=True,
        attachment__file_status=FileStatus.AVAILABLE,
    )
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_residence_attachment_links(
    *,
    residence: Residence,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[ResidenceAttachment]:
    """Vrať plná metadata příloh bydliště dostupná aktuálnímu actorovi."""

    return _get_visible_residence_attachment_links(
        residence=residence,
        actor=actor,
        enforce_private_access=True,
    )


def get_visible_residence_source_links(
    *,
    residence: Residence,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[ResidenceSource]:
    """Vrať zdroje viditelné v kontextu bydliště a jeho osoby."""

    visibility = {
        level: can_view_access_level(actor=actor, access_level=level)
        for level in _ACCESS_LEVELS
    }
    can_view_archived, can_view_deleted = _get_lifecycle_permissions(actor)
    current = _load_current_residence(residence)
    person = current.person
    if not (
        visibility.get(person.access_level, False)
        and (person.archived_at is None or can_view_archived)
        and (person.deleted_at is None or can_view_deleted)
        and visibility.get(current.access_level, False)
        and current.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit toto bydliště.")

    visible_levels = tuple(
        level for level, is_visible in visibility.items() if is_visible
    )
    return get_residence_source_links(residence=current).filter(
        _residence_person_lifecycle_filter(
            can_view_archived=can_view_archived,
            can_view_deleted=can_view_deleted,
        ),
        access_level__in=visible_levels,
        archived_at__isnull=True,
        residence__access_level__in=visible_levels,
        residence__deleted_at__isnull=True,
        residence__person__access_level__in=visible_levels,
        source__access_level__in=visible_levels,
        source__archived_at__isnull=True,
        source__deleted_at__isnull=True,
    )


def _get_visible_grave_site_attachment_links(
    *,
    grave_site: GraveSite,
    actor: AbstractBaseUser | AnonymousUser,
    enforce_private_access: bool,
) -> QuerySet[GraveSiteAttachment]:
    """Vrať dostupné přílohy viditelné v kontextu hrobového místa."""

    visibility = {
        level: can_view_access_level(actor=actor, access_level=level)
        for level in _ACCESS_LEVELS
    }
    current = _load_current_grave_site(grave_site)
    if not (
        visibility.get(current.access_level, False)
        and current.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit toto hrobové místo.")

    visible_levels = tuple(
        level for level, is_visible in visibility.items() if is_visible
    )
    queryset = get_grave_site_attachment_links(grave_site=current).filter(
        access_level__in=visible_levels,
        archived_at__isnull=True,
        grave_site__access_level__in=visible_levels,
        grave_site__deleted_at__isnull=True,
        attachment__access_level__in=visible_levels,
        attachment__archived_at__isnull=True,
        attachment__deleted_at__isnull=True,
        attachment__file_status=FileStatus.AVAILABLE,
    )
    if enforce_private_access:
        queryset = queryset.filter(_attachment_privacy_filter(actor))
    return queryset


def get_visible_grave_site_attachment_links(
    *,
    grave_site: GraveSite,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[GraveSiteAttachment]:
    """Vrať plná metadata příloh hrobového místa dostupná actorovi."""

    return _get_visible_grave_site_attachment_links(
        grave_site=grave_site,
        actor=actor,
        enforce_private_access=True,
    )


def _get_context_visible_attachment_link(
    *,
    link: AttachmentLinkModel,
    actor: AbstractBaseUser | AnonymousUser,
    for_update: bool = False,
) -> AttachmentLinkModel:
    """Načti link přes jeho schválený kontext bez private owner/grant filtru."""

    if not isinstance(link, AttachmentLinkModel) or link.pk is None:
        raise ValidationError(
            {
                "link": ValidationError(
                    "Vazba přílohy musí být uložená v databázi.",
                    code="attachment_link_unsaved",
                )
            }
        )
    if type(link) is PersonAttachment:
        queryset = _get_visible_person_attachment_links(
            person=Person(pk=link.person_id),
            actor=actor,
            enforce_private_access=False,
        )
    elif type(link) is EventAttachment:
        queryset = _get_visible_event_attachment_links(
            event=Event(pk=link.event_id),
            actor=actor,
            enforce_private_access=False,
        )
    elif type(link) is HealthRecordAttachment:
        queryset = _visible_health_record_attachment_links(
            actor=actor,
            enforce_private_access=False,
        )
    elif type(link) is RelationshipAttachment:
        queryset = _get_visible_relationship_attachment_links(
            relationship=Relationship(pk=link.relationship_id),
            actor=actor,
            enforce_private_access=False,
        )
    elif type(link) is ResidenceAttachment:
        queryset = _get_visible_residence_attachment_links(
            residence=Residence(pk=link.residence_id),
            actor=actor,
            enforce_private_access=False,
        )
    elif type(link) is GraveSiteAttachment:
        queryset = _get_visible_grave_site_attachment_links(
            grave_site=GraveSite(pk=link.grave_site_id),
            actor=actor,
            enforce_private_access=False,
        )
    else:
        raise PermissionDenied("K této vazbě přílohy nemáte oprávnění.")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    try:
        return queryset.get(pk=link.pk)
    except type(link).DoesNotExist as error:
        raise PermissionDenied(
            "K této vazbě přílohy nemáte oprávnění."
        ) from error


def _metadata_presentation(
    attachment: Attachment,
) -> AttachmentMetadataPresentation:
    return AttachmentMetadataPresentation(
        attachment_id=attachment.pk,
        label=str(attachment),
        display_name=attachment.display_name,
        description=attachment.description,
        original_filename=attachment.original_filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        sha256=attachment.sha256,
        file_status=attachment.file_status,
        privacy_status=attachment.privacy_status,
        access_level=attachment.access_level,
        creator_name=attachment.creator_name,
        provenance=attachment.provenance,
        original_owner=attachment.original_owner,
        language=attachment.language,
        technical_metadata=MappingProxyType(
            deepcopy(attachment.technical_metadata)
        ),
        created_by_id=attachment.created_by_id,
    )


def get_attachment_link_presentation(
    *,
    link: AttachmentLinkModel,
    actor: AbstractBaseUser | AnonymousUser,
) -> AttachmentMetadataPresentation | PrivateAttachmentPlaceholder:
    """Vrať plná bezpečná metadata, nebo jediný redigovaný placeholder."""

    current = _get_context_visible_attachment_link(link=link, actor=actor)
    attachment = current.attachment
    if (
        attachment.privacy_status == AttachmentPrivacyStatus.PRIVATE
        and not can_access_private_attachment(
            attachment=attachment,
            actor=actor,
        )
    ):
        return PrivateAttachmentPlaceholder()
    return _metadata_presentation(attachment)


def get_visible_grave_site_source_links(
    *,
    grave_site: GraveSite,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[GraveSiteSource]:
    """Vrať zdroje viditelné v kontextu hrobového místa."""

    visibility = {
        level: can_view_access_level(actor=actor, access_level=level)
        for level in _ACCESS_LEVELS
    }
    current = _load_current_grave_site(grave_site)
    if not (
        visibility.get(current.access_level, False)
        and current.deleted_at is None
    ):
        raise PermissionDenied("Nemáte oprávnění zobrazit toto hrobové místo.")

    visible_levels = tuple(
        level for level, is_visible in visibility.items() if is_visible
    )
    return get_grave_site_source_links(grave_site=current).filter(
        access_level__in=visible_levels,
        archived_at__isnull=True,
        grave_site__access_level__in=visible_levels,
        grave_site__deleted_at__isnull=True,
        source__access_level__in=visible_levels,
        source__archived_at__isnull=True,
        source__deleted_at__isnull=True,
    )
