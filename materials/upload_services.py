"""Actor-aware server-side upload use-case for protected attachments."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import BinaryIO, Callable, TypeVar

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from common.choices import AccessLevel
from common.permissions import (
    can_view_access_level,
    require_active_actor_permission,
)
from people.models import Person
from people.selectors import get_visible_people

from .choices import AttachmentPrivacyStatus, FileStatus
from .file_validation import staged_upload_file, validate_attachment_file
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    PersonAttachment,
)
from .services import (
    AttachmentLinkInput,
    create_person_attachment,
    get_or_create_owned_vault,
)
from .storage import ProtectedAttachmentStorage, ProtectedStorageError

__all__ = (
    "AttachmentUploadInput",
    "upload_attachment",
    "upload_person_attachment",
)

_Result = TypeVar("_Result")
_PERSON_ATTACHMENT_PERMISSION = "people.change_person"
_PERSON_ATTACHMENT_DENIAL = (
    "K nahrání přílohy k osobě nemáte oprávnění."
)


@dataclass(frozen=True, slots=True)
class AttachmentUploadInput:
    """Client metadata accepted by the protected upload use-case."""

    category: AttachmentCategory
    original_filename: str
    declared_mime_type: str
    privacy_status: str = AttachmentPrivacyStatus.STANDARD
    display_name: str = ""
    description: str = ""
    access_level: str = AccessLevel.PUBLIC


def upload_attachment(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    data: AttachmentUploadInput,
    stream: BinaryIO,
    storage: ProtectedAttachmentStorage | None = None,
) -> Attachment:
    """Validate and persist one blob in the current actor's own Vault."""

    return _upload_attachment(
        actor=actor,
        data=data,
        stream=stream,
        storage=storage,
        finalize=lambda attachment, _actor: attachment,
    )


def upload_person_attachment(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    person: Person,
    data: AttachmentUploadInput,
    role: AttachmentRole,
    stream: BinaryIO,
    storage: ProtectedAttachmentStorage | None = None,
) -> PersonAttachment:
    """Atomicky nahraj soubor a připoj jej k dostupné aktivní osobě."""

    current_actor = require_active_actor_permission(
        actor=actor,
        permission=_PERSON_ATTACHMENT_PERMISSION,
        denial_message=_PERSON_ATTACHMENT_DENIAL,
    )
    _validate_upload_input(data)
    _load_visible_active_person(person=person, actor=current_actor)
    _authorize_person_attachment_access(
        actor=current_actor,
        access_level=data.access_level,
    )

    def create_link(
        attachment: Attachment,
        locked_actor: AbstractBaseUser,
    ) -> PersonAttachment:
        authorized_actor = require_active_actor_permission(
            actor=locked_actor,
            permission=_PERSON_ATTACHMENT_PERMISSION,
            denial_message=_PERSON_ATTACHMENT_DENIAL,
        )
        current_person = _load_visible_active_person(
            person=person,
            actor=authorized_actor,
            lock=True,
        )
        _authorize_person_attachment_access(
            actor=authorized_actor,
            access_level=data.access_level,
        )
        return create_person_attachment(
            person=current_person,
            data=AttachmentLinkInput(
                attachment=attachment,
                role=role,
                access_level=data.access_level,
            ),
            created_by=authorized_actor,
        )

    return _upload_attachment(
        actor=current_actor,
        data=data,
        stream=stream,
        storage=storage,
        finalize=create_link,
    )


def _upload_attachment(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    data: AttachmentUploadInput,
    stream: BinaryIO,
    storage: ProtectedAttachmentStorage | None,
    finalize: Callable[[Attachment, AbstractBaseUser], _Result],
) -> _Result:
    """Persist one blob and finish its approved DB use-case in one boundary."""

    current_actor = _load_active_actor(actor)
    get_or_create_owned_vault(owner=current_actor)
    _validate_upload_input(data)
    protected_storage = storage or ProtectedAttachmentStorage()
    with staged_upload_file() as staged:
        validated = validate_attachment_file(
            source=stream,
            original_filename=data.original_filename,
            declared_mime_type=data.declared_mime_type,
            staged=staged,
        )
        storage_key = secrets.token_hex(32)
        blob_written = False
        vault = None
        try:
            with transaction.atomic():
                current_actor = _load_active_actor(actor, lock=True)
                vault = get_or_create_owned_vault(owner=current_actor)
                category = _load_active_category(data.category)
                attachment = Attachment(
                    vault=vault,
                    category=category,
                    original_filename=validated.original_filename,
                    storage_key=storage_key,
                    mime_type=validated.mime_type,
                    size_bytes=validated.size_bytes,
                    sha256=validated.sha256,
                    file_status=FileStatus.PENDING,
                    privacy_status=data.privacy_status,
                    display_name=data.display_name.strip(),
                    description=data.description.strip(),
                    access_level=data.access_level,
                    created_by=current_actor,
                )
                attachment.full_clean()
                attachment.save()
                protected_storage.write(vault, storage_key, staged)
                blob_written = True
                attachment.file_status = FileStatus.AVAILABLE
                attachment.full_clean()
                attachment.save(update_fields=("file_status", "updated_at"))
                return finalize(attachment, current_actor)
        except ProtectedStorageError as error:
            if blob_written and vault is not None:
                _compensating_delete(
                    storage=protected_storage,
                    vault=vault,
                    storage_key=storage_key,
                )
            raise ValidationError(
                {
                    "file": ValidationError(
                        "Soubor se nepodařilo bezpečně uložit.",
                        code="attachment_storage_write_failed",
                    )
                }
            ) from error
        except Exception:
            if blob_written and vault is not None:
                _compensating_delete(
                    storage=protected_storage,
                    vault=vault,
                    storage_key=storage_key,
                )
            raise


def _load_active_actor(
    actor: AbstractBaseUser | AnonymousUser,
    *,
    lock: bool = False,
) -> AbstractBaseUser:
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
    ):
        raise PermissionDenied("K nahrání přílohy nemáte oprávnění.")
    queryset = user_model._default_manager
    if lock:
        queryset = queryset.select_for_update()
    try:
        current_actor = queryset.get(pk=actor.pk)
    except user_model.DoesNotExist as error:
        raise PermissionDenied(
            "K nahrání přílohy nemáte oprávnění."
        ) from error
    if not current_actor.is_active:
        raise PermissionDenied("K nahrání přílohy nemáte oprávnění.")
    return current_actor


def _validate_upload_input(data: AttachmentUploadInput) -> None:
    if not isinstance(data, AttachmentUploadInput):
        raise ValidationError(
            {
                "data": ValidationError(
                    "Vstup uploadu není platný.",
                    code="attachment_upload_input_invalid",
                )
            }
        )
    if data.privacy_status not in AttachmentPrivacyStatus.values:
        raise ValidationError(
            {
                "privacy_status": ValidationError(
                    "Neznámý stav soukromí přílohy.",
                    code="privacy_status_invalid",
                )
            }
        )
    for field_name in ("display_name", "description"):
        if not isinstance(getattr(data, field_name), str):
            raise ValidationError(
                {
                    field_name: ValidationError(
                        "Textová metadata přílohy nejsou platná.",
                        code=f"attachment_{field_name}_invalid",
                    )
                }
            )
    if data.access_level not in AccessLevel.values:
        raise ValidationError(
            {
                "access_level": ValidationError(
                    "Neznámá úroveň přístupu.",
                    code="invalid_access_level",
                )
            }
        )


def _load_visible_active_person(
    *,
    person: Person,
    actor: AbstractBaseUser,
    lock: bool = False,
) -> Person:
    if not isinstance(person, Person) or person.pk is None:
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být uložená v databázi.",
                    code="person_unsaved",
                )
            }
        )
    queryset = get_visible_people(actor=actor)
    if lock:
        queryset = queryset.select_for_update()
    return queryset.get(pk=person.pk)


def _authorize_person_attachment_access(
    *,
    actor: AbstractBaseUser,
    access_level: str,
) -> None:
    if not can_view_access_level(actor=actor, access_level=access_level):
        raise PermissionDenied(_PERSON_ATTACHMENT_DENIAL)


def _load_active_category(category: AttachmentCategory) -> AttachmentCategory:
    if not isinstance(category, AttachmentCategory) or category.pk is None:
        raise ValidationError(
            {
                "category": ValidationError(
                    "Kategorie přílohy musí být uložená a aktivní.",
                    code="attachment_category_invalid",
                )
            }
        )
    try:
        return AttachmentCategory.objects.select_for_update().get(
            pk=category.pk,
            is_active=True,
        )
    except AttachmentCategory.DoesNotExist as error:
        raise ValidationError(
            {
                "category": ValidationError(
                    "Kategorie přílohy musí být uložená a aktivní.",
                    code="attachment_category_invalid",
                )
            }
        ) from error


def _compensating_delete(
    *,
    storage: ProtectedAttachmentStorage,
    vault,
    storage_key: str,
) -> None:
    try:
        storage.delete(vault, storage_key)
    except ProtectedStorageError:
        pass
