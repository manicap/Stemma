"""Transportně neutrální aplikační use-cases zdravotních záznamů."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet

from materials.models import HealthRecordAttachment, HealthRecordSource
from materials.selectors import (
    get_visible_health_record_attachment_links,
    get_visible_health_record_source_links,
)
from materials.services import (
    AttachmentLinkInput,
    create_health_record_attachment as create_attachment_service,
    update_health_record_attachment as update_attachment_service,
)
from materials.source_services import (
    SourceLinkInput,
    create_health_record_source as create_source_service,
    update_health_record_source as update_source_service,
)
from people.models import Person

from .models import HealthRecord
from .selectors import (
    get_archived_health_record_for_management as get_archived_record,
    get_visible_health_record,
    get_visible_health_records,
    list_archived_health_records_for_management,
)
from .services import (
    HealthRecordInput,
    archive_health_record as archive_health_record_service,
    create_health_record as create_health_record_service,
    restore_archived_health_record as restore_archived_health_record_service,
    update_health_record as update_health_record_service,
)

__all__ = (
    "archive_health_record",
    "create_health_record",
    "create_health_record_attachment",
    "create_health_record_source",
    "get_archived_health_record_for_management",
    "get_health_record_detail",
    "list_archived_health_records",
    "list_health_record_attachments",
    "list_health_records",
    "list_health_record_sources",
    "restore_archived_health_record",
    "update_health_record",
    "update_health_record_attachment",
    "update_health_record_source",
)


def archive_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
    reason: str = "",
) -> HealthRecord:
    """Archivuj zdravotní záznam přes autorizovanou lifecycle službu."""

    return archive_health_record_service(
        health_record=health_record,
        person=person,
        actor=actor,
        reason=reason,
    )


def restore_archived_health_record(
    *,
    health_record: HealthRecord,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Obnov archivovaný záznam přes autorizovanou lifecycle službu."""

    return restore_archived_health_record_service(
        health_record=health_record,
        person=person,
        actor=actor,
    )


def create_health_record(
    *,
    data: HealthRecordInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Vytvoř zdravotní záznam přes jedinou autorizovanou write službu."""

    return create_health_record_service(data=data, actor=actor)


def update_health_record(
    *,
    health_record: HealthRecord,
    data: HealthRecordInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Změň zdravotní záznam přes jedinou autorizovanou write službu."""

    return update_health_record_service(
        health_record=health_record,
        data=data,
        actor=actor,
    )


def create_health_record_attachment(
    *,
    health_record: HealthRecord,
    data: AttachmentLinkInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecordAttachment:
    """Vytvoř health attachment vazbu přes autorizovanou materials službu."""

    return create_attachment_service(
        health_record=health_record,
        data=data,
        actor=actor,
    )


def update_health_record_attachment(
    *,
    link: HealthRecordAttachment,
    health_record: HealthRecord,
    data: AttachmentLinkInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecordAttachment:
    """Změň health attachment vazbu přes autorizovanou materials službu."""

    return update_attachment_service(
        link=link,
        health_record=health_record,
        data=data,
        actor=actor,
    )


def create_health_record_source(
    *,
    health_record: HealthRecord,
    data: SourceLinkInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecordSource:
    """Vytvoř health source vazbu přes autorizovanou materials službu."""

    return create_source_service(
        health_record=health_record,
        data=data,
        actor=actor,
    )


def update_health_record_source(
    *,
    link: HealthRecordSource,
    health_record: HealthRecord,
    data: SourceLinkInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecordSource:
    """Změň health source vazbu přes autorizovanou materials službu."""

    return update_source_service(
        link=link,
        health_record=health_record,
        data=data,
        actor=actor,
    )


def list_health_record_attachments(
    *,
    health_record: HealthRecord,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecordAttachment]:
    """Vrať bezpečné přílohové vazby zdravotního záznamu."""

    return get_visible_health_record_attachment_links(
        health_record=health_record,
        actor=actor,
    )


def list_health_record_sources(
    *,
    health_record: HealthRecord,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecordSource]:
    """Vrať bezpečné zdrojové vazby zdravotního záznamu."""

    return get_visible_health_record_source_links(
        health_record=health_record,
        actor=actor,
    )


def list_health_records(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    """Vrať actorovi dostupné zdravotní záznamy konkrétní osoby."""

    return get_visible_health_records(person=person, actor=actor)


def list_archived_health_records(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> QuerySet[HealthRecord]:
    """Vrať archivované záznamy dostupné pro lifecycle management."""

    return list_archived_health_records_for_management(
        person=person,
        actor=actor,
    )


def get_archived_health_record_for_management(
    *,
    health_record_id: int,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> HealthRecord:
    """Vrať jeden archivovaný cíl pro potvrzení bezpečné obnovy."""

    return get_archived_record(
        health_record_id=health_record_id,
        person=person,
        actor=actor,
    )


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
