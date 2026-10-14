"""Streaming validation for the narrow M3.2 attachment allowlist."""

from __future__ import annotations

import hashlib
import unicodedata
import warnings
from dataclasses import dataclass
from pathlib import PurePosixPath
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Iterable

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
_READ_CHUNK_SIZE = 64 * 1024
_SPOOL_MEMORY_LIMIT = 1024 * 1024
_MAX_PDF_GRAPH_DEPTH = 100
_MAX_PDF_GRAPH_OBJECTS = 20_000

_TYPE_BY_EXTENSION = {
    ".pdf": ("application/pdf", "PDF"),
    ".jpg": ("image/jpeg", "JPEG"),
    ".jpeg": ("image/jpeg", "JPEG"),
    ".png": ("image/png", "PNG"),
}
_FALLBACK_BY_MIME = {
    "application/pdf": "soubor.pdf",
    "image/jpeg": "soubor.jpg",
    "image/png": "soubor.png",
}
_PDF_EMBEDDED_KEYS = {"/EmbeddedFiles", "/EF", "/AF"}
_PDF_ACTIVE_KEYS = {
    "/OpenAction",
    "/AA",
    "/A",
    "/JavaScript",
    "/JS",
    "/AcroForm",
    "/XFA",
    "/Trans",
}
_PDF_ACTIVE_SUBTYPES = {
    "/FileAttachment",
    "/Widget",
    "/RichMedia",
    "/3D",
    "/Movie",
    "/Sound",
    "/Screen",
}
_PDF_ACTION_TYPES = {
    "/JavaScript",
    "/Launch",
    "/URI",
    "/SubmitForm",
    "/ImportData",
    "/GoToR",
    "/GoToE",
    "/Rendition",
    "/Movie",
    "/Sound",
    "/Hide",
    "/SetOCGState",
    "/Trans",
    "/GoTo3DView",
}


@dataclass(frozen=True, slots=True)
class ValidatedAttachmentFile:
    """Sanitized metadata derived from one validated upload stream."""

    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def staged_upload_file() -> SpooledTemporaryFile[bytes]:
    """Return a bounded-memory seekable staging stream."""

    return SpooledTemporaryFile(max_size=_SPOOL_MEMORY_LIMIT, mode="w+b")


def validate_attachment_file(
    *,
    source: BinaryIO,
    original_filename: str,
    declared_mime_type: str,
    staged: BinaryIO,
) -> ValidatedAttachmentFile:
    """Copy, validate and hash an upload without trusting client metadata."""

    mime_type = _normalize_mime_type(declared_mime_type)
    filename = normalize_original_filename(
        original_filename,
        declared_mime_type=mime_type,
    )
    size_bytes = _copy_with_size_limit(source=source, target=staged)
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in _TYPE_BY_EXTENSION:
        _raise_validation(
            "original_filename",
            "Typ souboru není povolen.",
            "attachment_type_not_allowed",
        )
    expected_mime, expected_format = _TYPE_BY_EXTENSION[extension]
    if mime_type not in _FALLBACK_BY_MIME:
        _raise_validation(
            "mime_type",
            "Deklarovaný MIME typ není povolen.",
            "attachment_mime_not_allowed",
        )
    if mime_type != expected_mime:
        _raise_validation(
            "file",
            "Přípona a deklarovaný MIME typ si neodpovídají.",
            "attachment_type_mismatch",
        )
    _validate_magic(staged=staged, expected_format=expected_format)
    if expected_format == "PDF":
        _validate_pdf(staged)
    else:
        _validate_image(staged=staged, expected_format=expected_format)
    digest = _sha256(staged)
    staged.seek(0)
    return ValidatedAttachmentFile(
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=digest,
    )


def normalize_original_filename(
    value: str,
    *,
    declared_mime_type: str,
) -> str:
    """Normalize untrusted filename metadata without creating a path."""

    if not isinstance(value, str):
        _raise_validation(
            "original_filename",
            "Původní název souboru není platný.",
            "original_filename_invalid",
        )
    normalized = unicodedata.normalize("NFKC", value).replace("\\", "/")
    normalized = normalized.rsplit("/", maxsplit=1)[-1]
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    ).strip(" .")
    if not normalized:
        normalized = _FALLBACK_BY_MIME.get(
            declared_mime_type,
            "soubor",
        )
    suffix = PurePosixPath(normalized).suffix
    if len(normalized) > 255 and suffix:
        stem_limit = max(1, 255 - len(suffix))
        normalized = f"{normalized[:-len(suffix)][:stem_limit]}{suffix}"
    elif len(normalized) > 255:
        normalized = normalized[:255]
    if not normalized or len(normalized) > 255:
        _raise_validation(
            "original_filename",
            "Původní název souboru není platný.",
            "original_filename_invalid",
        )
    return normalized


def _normalize_mime_type(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _raise_validation(
            "mime_type",
            "Deklarovaný MIME typ není platný.",
            "attachment_mime_not_allowed",
        )
    return value.strip().lower()


def _source_chunks(source: BinaryIO) -> Iterable[bytes]:
    chunks = getattr(source, "chunks", None)
    if callable(chunks):
        yield from chunks(chunk_size=_READ_CHUNK_SIZE)
        return
    while True:
        chunk = source.read(_READ_CHUNK_SIZE)
        if not chunk:
            return
        yield chunk


def _copy_with_size_limit(*, source: BinaryIO, target: BinaryIO) -> int:
    size = 0
    try:
        for chunk in _source_chunks(source):
            if not isinstance(chunk, bytes):
                chunk = bytes(chunk)
            size += len(chunk)
            if size > MAX_ATTACHMENT_SIZE:
                _raise_validation(
                    "file",
                    "Soubor překračuje maximální velikost 25 MiB.",
                    "attachment_too_large",
                )
            target.write(chunk)
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(
            {
                "file": ValidationError(
                    "Soubor se nepodařilo bezpečně načíst.",
                    code="attachment_content_invalid",
                )
            }
        ) from error
    if size == 0:
        _raise_validation(
            "file",
            "Soubor je prázdný nebo poškozený.",
            "attachment_content_invalid",
        )
    target.seek(0)
    return size


def _validate_magic(*, staged: BinaryIO, expected_format: str) -> None:
    staged.seek(0)
    header = staged.read(8)
    signatures = {
        "PDF": b"%PDF-",
        "JPEG": b"\xff\xd8\xff",
        "PNG": b"\x89PNG\r\n\x1a\n",
    }
    if not header.startswith(signatures[expected_format]):
        _raise_validation(
            "file",
            "Obsah souboru neodpovídá deklarovanému typu.",
            "attachment_type_mismatch",
        )
    staged.seek(0)


def _validate_image(*, staged: BinaryIO, expected_format: str) -> None:
    try:
        _validate_image_envelope(
            staged=staged,
            expected_format=expected_format,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            staged.seek(0)
            with Image.open(staged) as image:
                if image.format != expected_format:
                    _raise_validation(
                        "file",
                        "Obsah obrázku neodpovídá deklarovanému typu.",
                        "attachment_type_mismatch",
                    )
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    _raise_validation(
                        "file",
                        "Rozměry obrázku překračují bezpečný limit.",
                        "attachment_content_invalid",
                    )
                image.verify()
            staged.seek(0)
            with Image.open(staged) as image:
                image.load()
    except ValidationError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as error:
        raise ValidationError(
            {
                "file": ValidationError(
                    "Obrázek je poškozený nebo nebezpečný.",
                    code="attachment_content_invalid",
                )
            }
        ) from error
    finally:
        staged.seek(0)


def _validate_image_envelope(*, staged: BinaryIO, expected_format: str) -> None:
    endings = {
        "JPEG": b"\xff\xd9",
        "PNG": b"\x00\x00\x00\x00IEND\xaeB\x60\x82",
    }
    expected_ending = endings[expected_format]
    staged.seek(0, 2)
    size = staged.tell()
    staged.seek(max(0, size - len(expected_ending)))
    if staged.read() != expected_ending:
        _raise_validation(
            "file",
            "Obrázek je poškozený nebo obsahuje data za svým koncem.",
            "attachment_content_invalid",
        )
    staged.seek(0)


def _validate_pdf(staged: BinaryIO) -> None:
    try:
        staged.seek(0, 2)
        size = staged.tell()
        staged.seek(max(0, size - 1024))
        if not staged.read().rstrip(b"\x00\t\n\x0c\r ").endswith(b"%%EOF"):
            _raise_validation(
                "file",
                "PDF je poškozené.",
                "attachment_content_invalid",
            )
        staged.seek(0)
        reader = PdfReader(staged, strict=True)
        if reader.is_encrypted:
            _raise_validation(
                "file",
                "Šifrované PDF není povoleno.",
                "attachment_pdf_encrypted",
            )
        if len(reader.pages) == 0:
            _raise_validation(
                "file",
                "PDF neobsahuje žádnou stránku.",
                "attachment_content_invalid",
            )
        _scan_pdf_graph(reader.root_object)
    except ValidationError:
        raise
    except Exception as error:
        raise ValidationError(
            {
                "file": ValidationError(
                    "PDF je poškozené nebo podezřelé.",
                    code="attachment_content_invalid",
                )
            }
        ) from error
    finally:
        staged.seek(0)


def _scan_pdf_graph(root: object) -> None:
    stack = [(root, 0)]
    indirect_seen: set[tuple[int, int]] = set()
    direct_seen: set[int] = set()
    visited = 0
    while stack:
        value, depth = stack.pop()
        if depth > _MAX_PDF_GRAPH_DEPTH:
            _raise_pdf_active_content()
        if isinstance(value, IndirectObject):
            reference = (value.idnum, value.generation)
            if reference in indirect_seen:
                continue
            indirect_seen.add(reference)
            value = value.get_object()
        if isinstance(value, (DictionaryObject, ArrayObject)):
            identity = id(value)
            if identity in direct_seen:
                continue
            direct_seen.add(identity)
            visited += 1
            if visited > _MAX_PDF_GRAPH_OBJECTS:
                _raise_pdf_active_content()
        if isinstance(value, DictionaryObject):
            keys = {str(key) for key in value.keys()}
            if keys & _PDF_EMBEDDED_KEYS:
                _raise_validation(
                    "file",
                    "PDF obsahuje vložený soubor.",
                    "attachment_pdf_embedded_file",
                )
            if keys & _PDF_ACTIVE_KEYS:
                _raise_pdf_active_content()
            object_type = str(value.get("/Type", ""))
            subtype = str(value.get("/Subtype", ""))
            action_type = str(value.get("/S", ""))
            if object_type in {"/EmbeddedFile", "/Filespec"}:
                _raise_validation(
                    "file",
                    "PDF obsahuje vložený soubor.",
                    "attachment_pdf_embedded_file",
                )
            if subtype in _PDF_ACTIVE_SUBTYPES:
                _raise_pdf_active_content()
            if action_type in _PDF_ACTION_TYPES:
                _raise_pdf_active_content()
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, ArrayObject):
            stack.extend((item, depth + 1) for item in value)


def _raise_pdf_active_content() -> None:
    _raise_validation(
        "file",
        "PDF obsahuje aktivní nebo nebezpečný obsah.",
        "attachment_pdf_active_content",
    )


def _sha256(staged: BinaryIO) -> str:
    digest = hashlib.sha256()
    staged.seek(0)
    while True:
        chunk = staged.read(_READ_CHUNK_SIZE)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def _raise_validation(field: str, message: str, code: str) -> None:
    raise ValidationError({field: ValidationError(message, code=code)})
