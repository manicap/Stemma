"""Actor-aware server-side upload use-case for protected attachments."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import BinaryIO

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .choices import AttachmentPrivacyStatus, FileStatus
from .file_validation import staged_upload_file, validate_attachment_file
from .models import Attachment, AttachmentCategory
from .services import get_or_create_owned_vault
from .storage import ProtectedAttachmentStorage, ProtectedStorageError

__all__ = ("AttachmentUploadInput", "upload_attachment")


@dataclass(frozen=True, slots=True)
class AttachmentUploadInput:
    """Client metadata accepted by the protected upload use-case."""

    category: AttachmentCategory
    original_filename: str
    declared_mime_type: str
    privacy_status: str = AttachmentPrivacyStatus.STANDARD


def upload_attachment(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    data: AttachmentUploadInput,
    stream: BinaryIO,
    storage: ProtectedAttachmentStorage | None = None,
) -> Attachment:
    """Validate and persist one blob in the current actor's own Vault."""

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
                    created_by=current_actor,
                )
                attachment.full_clean()
                attachment.save()
                protected_storage.write(vault, storage_key, staged)
                blob_written = True
                attachment.file_status = FileStatus.AVAILABLE
                attachment.full_clean()
                attachment.save(update_fields=("file_status", "updated_at"))
                return attachment
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
