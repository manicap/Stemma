import hashlib
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject

from .choices import AttachmentPrivacyStatus, FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    EventAttachment,
    GraveSiteAttachment,
    HealthRecordAttachment,
    PersonAttachment,
    PlaceAttachment,
    RelationshipAttachment,
    ResidenceAttachment,
)
from .storage import ProtectedAttachmentStorage, ProtectedStorageError
from .upload_services import AttachmentUploadInput, upload_attachment


class RecordingStorage:
    def __init__(self, wrapped: ProtectedAttachmentStorage) -> None:
        self.wrapped = wrapped
        self.writes: list[tuple[object, str]] = []
        self.deletes: list[tuple[object, str]] = []
        self.pending_seen = False

    def write(self, vault, storage_key, stream) -> None:
        self.pending_seen = Attachment.objects.filter(
            storage_key=storage_key,
            file_status=FileStatus.PENDING,
        ).exists()
        self.wrapped.write(vault, storage_key, stream)
        self.writes.append((vault, storage_key))

    def delete(self, vault, storage_key) -> None:
        self.deletes.append((vault, storage_key))
        self.wrapped.delete(vault, storage_key)

    def exists(self, vault, storage_key) -> bool:
        return self.wrapped.exists(vault, storage_key)


class FailingWriteStorage:
    def write(self, vault, storage_key, stream) -> None:
        raise ProtectedStorageError("internal storage detail")

    def delete(self, vault, storage_key) -> None:
        raise AssertionError("delete must not run after an unconfirmed write")


class OversizeStream:
    def __init__(self) -> None:
        self.chunks_read = 0

    def chunks(self, chunk_size=None):
        for _ in range(26):
            self.chunks_read += 1
            yield b"x" * (1024 * 1024)
        raise AssertionError("reader did not stop at the size limit")


class UnreadableStream:
    def read(self, size=-1):
        raise AssertionError("unauthorized stream must not be read")


class AttachmentUploadTests(TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.actor = get_user_model().objects.create_user(username="uploader")
        self.category = AttachmentCategory.objects.create(
            code="upload-document",
            name="Upload dokument",
        )
        self.storage = ProtectedAttachmentStorage()

    def upload(
        self,
        content: bytes,
        *,
        filename: str = "document.pdf",
        mime_type: str = "application/pdf",
        actor=None,
        privacy_status: str = AttachmentPrivacyStatus.STANDARD,
        storage=None,
    ) -> Attachment:
        return upload_attachment(
            actor=self.actor if actor is None else actor,
            data=AttachmentUploadInput(
                category=self.category,
                original_filename=filename,
                declared_mime_type=mime_type,
                privacy_status=privacy_status,
            ),
            stream=SimpleUploadedFile(filename, content, content_type=mime_type),
            storage=storage or self.storage,
        )

    def test_valid_pdf_jpeg_and_png_are_stored_and_available(self) -> None:
        cases = (
            ("document.pdf", "application/pdf", self.pdf()),
            ("photo.jpg", "image/jpeg", self.image("JPEG")),
            ("photo.jpeg", "image/jpeg", self.image("JPEG")),
            ("scan.png", "image/png", self.image("PNG")),
        )
        for filename, mime_type, content in cases:
            with self.subTest(filename=filename):
                attachment = self.upload(
                    content,
                    filename=filename,
                    mime_type=mime_type,
                )
                self.assertEqual(attachment.file_status, FileStatus.AVAILABLE)
                self.assertEqual(attachment.vault, self.actor.vault)
                self.assertEqual(attachment.created_by, self.actor)
                self.assertEqual(attachment.size_bytes, len(content))
                self.assertEqual(
                    attachment.sha256,
                    hashlib.sha256(content).hexdigest(),
                )
                self.assertRegex(attachment.storage_key, r"^[0-9a-f]{64}$")
                with self.storage.open(
                    attachment.vault,
                    attachment.storage_key,
                ) as stored:
                    self.assertEqual(stored.read(), content)

    def test_pending_is_observable_before_blob_then_available(self) -> None:
        recording = RecordingStorage(self.storage)

        attachment = self.upload(self.pdf(), storage=recording)

        self.assertTrue(recording.pending_seen)
        self.assertEqual(attachment.file_status, FileStatus.AVAILABLE)
        self.assertTrue(
            Attachment.objects.filter(
                pk=attachment.pk,
                file_status=FileStatus.AVAILABLE,
            ).exists()
        )

    def test_duplicate_sha256_creates_distinct_attachment_and_blob(self) -> None:
        content = self.pdf()

        first = self.upload(content, filename="first.pdf")
        second = self.upload(content, filename="second.pdf")

        self.assertEqual(first.sha256, second.sha256)
        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(first.storage_key, second.storage_key)
        self.assertEqual(Attachment.objects.filter(sha256=first.sha256).count(), 2)

    def test_filename_is_metadata_only_and_normalized_safely(self) -> None:
        normalized = self.upload(
            self.pdf(),
            filename="../folder\\Ａ\x00.pdf",
        )
        fallback = self.upload(self.pdf(), filename="\x00\x01")
        long_name = self.upload(
            self.pdf(),
            filename=f"{'a' * 300}.pdf",
        )

        self.assertEqual(normalized.original_filename, "A.pdf")
        self.assertEqual(fallback.original_filename, "soubor.pdf")
        self.assertEqual(len(long_name.original_filename), 255)
        self.assertTrue(long_name.original_filename.endswith(".pdf"))
        for attachment in (normalized, fallback, long_name):
            self.assertNotIn(attachment.original_filename, attachment.storage_key)

    def test_size_limit_stops_stream_immediately(self) -> None:
        source = OversizeStream()

        with self.assertRaises(ValidationError) as context:
            upload_attachment(
                actor=self.actor,
                data=AttachmentUploadInput(
                    category=self.category,
                    original_filename="large.pdf",
                    declared_mime_type="application/pdf",
                ),
                stream=source,
                storage=self.storage,
            )

        self.assertEqual(
            context.exception.error_dict["file"][0].code,
            "attachment_too_large",
        )
        self.assertEqual(source.chunks_read, 26)
        self.assertEqual(Attachment.objects.count(), 0)

    def test_extension_mime_and_signature_are_independently_validated(self) -> None:
        cases = (
            (
                "blocked.svg",
                "image/svg+xml",
                b"<svg/>",
                "attachment_type_not_allowed",
            ),
            ("file.pdf", "text/html", self.pdf(), "attachment_mime_not_allowed"),
            ("file.pdf", "image/png", self.pdf(), "attachment_type_mismatch"),
            (
                "renamed.pdf",
                "application/pdf",
                b"MZ executable",
                "attachment_type_mismatch",
            ),
        )
        for filename, mime_type, content, code in cases:
            with self.subTest(filename=filename, mime_type=mime_type):
                with self.assertRaises(ValidationError) as context:
                    self.upload(
                        content,
                        filename=filename,
                        mime_type=mime_type,
                    )
                field = next(iter(context.exception.error_dict))
                self.assertEqual(context.exception.error_dict[field][0].code, code)

    def test_corrupt_image_and_pdf_are_rejected(self) -> None:
        cases = (
            ("broken.jpg", "image/jpeg", b"\xff\xd8\xffbroken"),
            ("broken.png", "image/png", b"\x89PNG\r\n\x1a\nbroken"),
            ("broken.pdf", "application/pdf", self.pdf()[:-5]),
        )
        for filename, mime_type, content in cases:
            with self.subTest(filename=filename):
                with self.assertRaises(ValidationError) as context:
                    self.upload(
                        content,
                        filename=filename,
                        mime_type=mime_type,
                    )
                self.assertEqual(
                    context.exception.error_dict["file"][0].code,
                    "attachment_content_invalid",
                )

    def test_trailing_payload_after_image_end_is_rejected(self) -> None:
        cases = (
            ("polyglot.jpg", "image/jpeg", self.image("JPEG")),
            ("polyglot.png", "image/png", self.image("PNG")),
        )
        for filename, mime_type, content in cases:
            with self.subTest(filename=filename):
                with self.assertRaises(ValidationError) as context:
                    self.upload(
                        content + b"<script>alert(1)</script>",
                        filename=filename,
                        mime_type=mime_type,
                    )
                self.assertEqual(
                    context.exception.error_dict["file"][0].code,
                    "attachment_content_invalid",
                )

    def test_encrypted_active_and_embedded_pdf_are_rejected(self) -> None:
        cases = (
            (self.pdf(encrypted=True), "attachment_pdf_encrypted"),
            (self.pdf(javascript=True), "attachment_pdf_active_content"),
            (self.pdf(embedded=True), "attachment_pdf_embedded_file"),
        )
        for content, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as context:
                    self.upload(content)
                self.assertEqual(context.exception.error_dict["file"][0].code, code)

    def test_pdf_form_and_open_action_are_rejected(self) -> None:
        cases = (
            self.pdf(acro_form=True),
            self.pdf(open_action=True),
        )
        for content in cases:
            with self.subTest(content_length=len(content)):
                with self.assertRaises(ValidationError) as context:
                    self.upload(content)
                self.assertEqual(
                    context.exception.error_dict["file"][0].code,
                    "attachment_pdf_active_content",
                )

    def test_image_pixel_limit_is_fail_closed(self) -> None:
        with (
            patch("materials.file_validation.MAX_IMAGE_PIXELS", 1),
            self.assertRaises(ValidationError) as context,
        ):
            self.upload(
                self.image("PNG"),
                filename="large-pixels.png",
                mime_type="image/png",
            )

        self.assertEqual(
            context.exception.error_dict["file"][0].code,
            "attachment_content_invalid",
        )

    def test_trailing_payload_after_pdf_eof_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            self.upload(self.pdf() + b"<script>alert(1)</script>")

        self.assertEqual(
            context.exception.error_dict["file"][0].code,
            "attachment_content_invalid",
        )

    def test_standard_and_private_values_are_supported(self) -> None:
        standard = self.upload(self.pdf(), filename="standard.pdf")
        private = self.upload(
            self.pdf(),
            filename="private.pdf",
            privacy_status=AttachmentPrivacyStatus.PRIVATE,
        )

        self.assertEqual(
            standard.privacy_status,
            AttachmentPrivacyStatus.STANDARD,
        )
        self.assertEqual(
            private.privacy_status,
            AttachmentPrivacyStatus.PRIVATE,
        )

        with self.assertRaises(ValidationError) as context:
            self.upload(self.pdf(), privacy_status="unknown")
        self.assertEqual(
            context.exception.error_dict["privacy_status"][0].code,
            "privacy_status_invalid",
        )

    def test_invalid_filename_and_inactive_category_are_rejected(self) -> None:
        with self.assertRaises(ValidationError) as filename_context:
            upload_attachment(
                actor=self.actor,
                data=AttachmentUploadInput(
                    category=self.category,
                    original_filename=None,
                    declared_mime_type="application/pdf",
                ),
                stream=BytesIO(self.pdf()),
                storage=self.storage,
            )
        self.assertEqual(
            filename_context.exception.error_dict["original_filename"][0].code,
            "original_filename_invalid",
        )

        self.category.is_active = False
        self.category.save(update_fields={"is_active"})
        with self.assertRaises(ValidationError) as category_context:
            self.upload(self.pdf())
        self.assertEqual(
            category_context.exception.error_dict["category"][0].code,
            "attachment_category_invalid",
        )

    def test_anonymous_inactive_and_missing_actor_are_denied(self) -> None:
        inactive = get_user_model().objects.create_user(
            username="inactive-uploader",
            is_active=False,
        )
        missing = get_user_model().objects.create_user(username="missing-uploader")
        missing.vault.delete()
        missing.delete()

        for actor in (AnonymousUser(), inactive, missing):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    self.upload(self.pdf(), actor=actor)

        with self.assertRaises(PermissionDenied):
            upload_attachment(
                actor=AnonymousUser(),
                data=AttachmentUploadInput(
                    category=self.category,
                    original_filename="unread.pdf",
                    declared_mime_type="application/pdf",
                ),
                stream=UnreadableStream(),
                storage=self.storage,
            )

    def test_staff_and_superuser_can_only_upload_to_own_vault(self) -> None:
        actors = (
            get_user_model().objects.create_user(
                username="staff-uploader",
                is_staff=True,
            ),
            get_user_model().objects.create_superuser(
                username="super-uploader",
                password="strong-test-password",
            ),
        )
        foreign_vault = self.actor.vault
        for actor in actors:
            with self.subTest(actor=actor.username):
                attachment = self.upload(
                    self.pdf(),
                    filename=f"{actor.username}.pdf",
                    actor=actor,
                )
                self.assertEqual(attachment.vault, actor.vault)
                self.assertNotEqual(attachment.vault, foreign_vault)

    def test_storage_failure_rolls_back_metadata_without_leaking_details(self) -> None:
        with self.assertRaises(ValidationError) as context:
            self.upload(self.pdf(), storage=FailingWriteStorage())

        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(
            context.exception.error_dict["file"][0].code,
            "attachment_storage_write_failed",
        )
        self.assertNotIn("internal", str(context.exception))

    def test_failure_after_write_rolls_back_and_deletes_blob(self) -> None:
        recording = RecordingStorage(self.storage)
        original_full_clean = Attachment.full_clean
        calls = 0

        def fail_second_validation(instance, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("metadata confirmation failed")
            return original_full_clean(instance, *args, **kwargs)

        with (
            patch.object(Attachment, "full_clean", fail_second_validation),
            self.assertRaisesRegex(RuntimeError, "metadata confirmation failed"),
        ):
            self.upload(self.pdf(), storage=recording)

        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(len(recording.writes), 1)
        self.assertEqual(recording.deletes, recording.writes)
        vault, storage_key = recording.writes[0]
        self.assertFalse(recording.exists(vault, storage_key))

    def test_cleanup_failure_does_not_mask_original_failure(self) -> None:
        recording = RecordingStorage(self.storage)
        original_full_clean = Attachment.full_clean
        calls = 0

        def fail_second_validation(instance, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("original metadata failure")
            return original_full_clean(instance, *args, **kwargs)

        with (
            patch.object(Attachment, "full_clean", fail_second_validation),
            patch.object(
                recording,
                "delete",
                side_effect=ProtectedStorageError("cleanup detail"),
            ),
            self.assertRaisesRegex(RuntimeError, "original metadata failure"),
        ):
            self.upload(self.pdf(), storage=recording)

        self.assertEqual(Attachment.objects.count(), 0)

    def test_upload_creates_no_domain_link(self) -> None:
        self.upload(self.pdf())

        for model in (
            PersonAttachment,
            EventAttachment,
            RelationshipAttachment,
            ResidenceAttachment,
            GraveSiteAttachment,
            PlaceAttachment,
            HealthRecordAttachment,
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), 0)

    @staticmethod
    def image(image_format: str) -> bytes:
        stream = BytesIO()
        Image.new("RGB", (2, 2), color="white").save(
            stream,
            format=image_format,
        )
        return stream.getvalue()

    @staticmethod
    def pdf(
        *,
        encrypted: bool = False,
        javascript: bool = False,
        embedded: bool = False,
        acro_form: bool = False,
        open_action: bool = False,
    ) -> bytes:
        stream = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        if encrypted:
            writer.encrypt("secret")
        if javascript:
            writer.add_js("app.alert('unsafe')")
        if embedded:
            writer.add_attachment("embedded.txt", b"unsafe")
        if acro_form:
            writer.root_object[NameObject("/AcroForm")] = DictionaryObject()
        if open_action:
            writer.root_object[NameObject("/OpenAction")] = DictionaryObject(
                {
                    NameObject("/S"): NameObject("/JavaScript"),
                    NameObject("/JS"): NameObject("/unsafe"),
                }
            )
        writer.write(stream)
        return stream.getvalue()
