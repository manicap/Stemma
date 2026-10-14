"""Private Vault-aware storage boundary for attachment blobs."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files import File
from django.core.files.storage import FileSystemStorage

from .models import Vault

_OPAQUE_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ProtectedStorageError(Exception):
    """Sanitized failure raised by the protected storage boundary."""


def validate_protected_storage_root() -> None:
    """Reject any overlap with a directory intended for public delivery."""

    try:
        protected_root = Path(settings.PROTECTED_ATTACHMENTS_ROOT).resolve()
        public_roots = [
            root
            for root in (
                getattr(settings, "MEDIA_ROOT", None),
                getattr(settings, "STATIC_ROOT", None),
            )
            if root
        ]
        for entry in getattr(settings, "STATICFILES_DIRS", ()):
            public_roots.append(
                entry[1]
                if isinstance(entry, (list, tuple)) and len(entry) == 2
                else entry
            )
        for public_root_setting in public_roots:
            public_root = Path(public_root_setting).resolve()
            if (
                protected_root == public_root
                or protected_root in public_root.parents
                or public_root in protected_root.parents
            ):
                raise ImproperlyConfigured(
                    "Protected attachment storage must be separated from "
                    "public media and static directories."
                )
    except (OSError, TypeError, ValueError) as error:
        raise ImproperlyConfigured(
            "Protected attachment storage root is invalid."
        ) from error


class _PrivateFileSystemStorage(FileSystemStorage):
    """Filesystem backend that never exposes a public URL."""

    def url(self, name: str) -> str:
        raise ProtectedStorageError("Privátní soubor nemá veřejnou URL.")


class ProtectedAttachmentStorage:
    """Store opaque blob keys in a namespace owned by one Vault."""

    def __init__(self) -> None:
        validate_protected_storage_root()
        self._storage = _PrivateFileSystemStorage(
            location=settings.PROTECTED_ATTACHMENTS_ROOT,
            base_url=None,
            file_permissions_mode=(
                settings.PROTECTED_ATTACHMENTS_FILE_PERMISSIONS
            ),
            directory_permissions_mode=(
                settings.PROTECTED_ATTACHMENTS_DIRECTORY_PERMISSIONS
            ),
            allow_overwrite=False,
        )

    def write(
        self,
        vault: Vault,
        storage_key: str,
        stream: BinaryIO,
    ) -> None:
        """Write one new blob without exposing or accepting physical paths."""

        name = self._storage_name(vault, storage_key)
        if self._storage.exists(name):
            raise ProtectedStorageError("Cílový objekt již existuje.")
        try:
            stream.seek(0)
            saved_name = self._storage.save(name, File(stream))
            if saved_name != name:
                self._safe_delete(saved_name)
                raise ProtectedStorageError("Cílový objekt již existuje.")
        except ProtectedStorageError:
            raise
        except Exception as error:
            self._safe_delete(name)
            raise ProtectedStorageError(
                "Blob se nepodařilo bezpečně uložit."
            ) from error

    def open(self, vault: Vault, storage_key: str) -> File:
        """Open a blob for internal server-side processing only."""

        name = self._storage_name(vault, storage_key)
        try:
            return self._storage.open(name, mode="rb")
        except Exception as error:
            raise ProtectedStorageError(
                "Blob se nepodařilo bezpečně otevřít."
            ) from error

    def delete(self, vault: Vault, storage_key: str) -> None:
        """Delete a blob without revealing its physical location."""

        name = self._storage_name(vault, storage_key)
        try:
            self._storage.delete(name)
        except Exception as error:
            raise ProtectedStorageError(
                "Blob se nepodařilo bezpečně odstranit."
            ) from error

    def exists(self, vault: Vault, storage_key: str) -> bool:
        """Support integrity checks without exposing a path or URL."""

        name = self._storage_name(vault, storage_key)
        try:
            return self._storage.exists(name)
        except Exception as error:
            raise ProtectedStorageError(
                "Stav blobu se nepodařilo bezpečně ověřit."
            ) from error

    def _storage_name(self, vault: Vault, storage_key: str) -> str:
        if (
            not isinstance(vault, Vault)
            or vault.pk is None
            or not Vault.objects.filter(pk=vault.pk).exists()
        ):
            raise ProtectedStorageError("Vault není platný.")
        if (
            not isinstance(storage_key, str)
            or not _OPAQUE_KEY_PATTERN.fullmatch(storage_key)
        ):
            raise ProtectedStorageError("Storage key není platný.")
        name = PurePosixPath(
            "vaults",
            str(vault.pk),
            storage_key[:2],
            storage_key,
        ).as_posix()
        if name.startswith("/") or ".." in PurePosixPath(name).parts:
            raise ProtectedStorageError("Neplatný interní název blobu.")
        return name

    def _safe_delete(self, name: str) -> None:
        try:
            self._storage.delete(name)
        except Exception:
            pass
