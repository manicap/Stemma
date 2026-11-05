"""Context-authorized delivery of protected attachment blobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Final

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)

from events.models import Event
from health.models import HealthRecord
from people.models import Person, Relationship
from places.models import GraveSite, Residence

from .access_policy import can_access_private_attachment
from .choices import AttachmentPrivacyStatus
from .file_validation import normalize_original_filename
from .models import (
    AttachmentLinkModel,
    EventAttachment,
    GraveSiteAttachment,
    HealthRecordAttachment,
    PersonAttachment,
    ResidenceAttachment,
    RelationshipAttachment,
)
from .selectors import _get_context_visible_attachment_link
from .storage import ProtectedAttachmentStorage, ProtectedStorageError

__all__ = (
    "AttachmentDelivery",
    "AttachmentDeliveryUnavailable",
    "get_attachment_delivery",
)


class AttachmentDeliveryUnavailable(Exception):
    """Fail-closed public error for an unavailable delivery target."""


@dataclass(frozen=True, slots=True)
class AttachmentDelivery:
    """Authorized stream and safe HTTP metadata for one attachment."""

    content: BinaryIO
    filename: str
    content_type: str


@dataclass(frozen=True, slots=True)
class _ContextDefinition:
    link_model: type[AttachmentLinkModel]
    target_model: type[object]
    target_field: str


_CONTEXTS: Final[dict[str, _ContextDefinition]] = {
    "person": _ContextDefinition(PersonAttachment, Person, "person"),
    "event": _ContextDefinition(EventAttachment, Event, "event"),
    "health-record": _ContextDefinition(
        HealthRecordAttachment,
        HealthRecord,
        "health_record",
    ),
    "relationship": _ContextDefinition(
        RelationshipAttachment,
        Relationship,
        "relationship",
    ),
    "residence": _ContextDefinition(
        ResidenceAttachment,
        Residence,
        "residence",
    ),
    "grave-site": _ContextDefinition(
        GraveSiteAttachment,
        GraveSite,
        "grave_site",
    ),
}
_DELIVERABLE_MIME_TYPES: Final = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def _unavailable() -> AttachmentDeliveryUnavailable:
    return AttachmentDeliveryUnavailable("Příloha není dostupná.")


def _load_context_link(
    *,
    context_type: str,
    context_id: int,
    link_id: int,
) -> AttachmentLinkModel:
    definition = _CONTEXTS.get(context_type)
    if definition is None or context_id < 1 or link_id < 1:
        raise _unavailable()
    try:
        target = definition.target_model(pk=context_id)
        return definition.link_model(
            pk=link_id,
            **{definition.target_field: target},
        )
    except (TypeError, ValueError) as error:
        raise _unavailable() from error


def get_attachment_delivery(
    *,
    context_type: str,
    context_id: int,
    link_id: int,
    actor: AbstractBaseUser | AnonymousUser,
    storage: ProtectedAttachmentStorage | None = None,
) -> AttachmentDelivery:
    """Authorize a concrete context/link and open its private storage blob."""

    link = _load_context_link(
        context_type=context_type,
        context_id=context_id,
        link_id=link_id,
    )
    try:
        current = _get_context_visible_attachment_link(
            link=link,
            actor=actor,
        )
        attachment = current.attachment
        if attachment.privacy_status == AttachmentPrivacyStatus.PRIVATE:
            if not can_access_private_attachment(
                attachment=attachment,
                actor=actor,
            ):
                raise _unavailable()
        elif attachment.privacy_status != AttachmentPrivacyStatus.STANDARD:
            raise _unavailable()
        if attachment.mime_type not in _DELIVERABLE_MIME_TYPES:
            raise _unavailable()
        filename = normalize_original_filename(
            attachment.original_filename,
            declared_mime_type=attachment.mime_type,
        )
        content = (storage or ProtectedAttachmentStorage()).open(
            attachment.vault,
            attachment.storage_key,
        )
    except AttachmentDeliveryUnavailable:
        raise
    except (
        ObjectDoesNotExist,
        PermissionDenied,
        ProtectedStorageError,
        ValidationError,
    ) as error:
        raise _unavailable() from error
    return AttachmentDelivery(
        content=content,
        filename=filename,
        content_type=attachment.mime_type,
    )
