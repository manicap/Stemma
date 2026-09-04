"""Transportně neutrální aplikační use-cases zdravotních záznamů."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet

from materials.models import HealthRecordAttachment
from materials.services import (
    AttachmentLinkInput,
    create_health_record_attachment as create_attachment_service,
    update_health_record_attachment as update_attachment_service,
)
from people.models import Person

from .models import HealthRecord
from .selectors import get_visible_health_record, get_visible_health_records
from .services import (
    HealthRecordInput,
    create_health_record as create_health_record_service,
    update_health_record as update_health_record_service,
)

__all__ = (
    "create_health_record",
    "create_health_record_attachment",
    "get_health_record_detail",
    "list_health_records",
    "update_health_record",
    "update_health_record_attachment",
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
