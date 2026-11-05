from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter

from common.choices import AccessLevel
from people.models import Person

from .choices import FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    PersonAttachment,
)
from .storage import ProtectedAttachmentStorage, ProtectedStorageError
from .upload_services import (
    AttachmentUploadInput,
    upload_person_attachment,
)


class RecordingStorage:
    def __init__(self, wrapped: ProtectedAttachmentStorage) -> None:
        self.wrapped = wrapped
        self.writes: list[tuple[object, str]] = []
        self.deletes: list[tuple[object, str]] = []

    def write(self, vault, storage_key, stream) -> None:
        self.wrapped.write(vault, storage_key, stream)
        self.writes.append((vault, storage_key))

    def delete(self, vault, storage_key) -> None:
        self.deletes.append((vault, storage_key))
        self.wrapped.delete(vault, storage_key)

    def exists(self, vault, storage_key) -> bool:
        return self.wrapped.exists(vault, storage_key)


class UnreadableStream:
    def read(self, size=-1):
        raise AssertionError("unauthorized stream must not be read")


class PersonAttachmentUploadTests(TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.actor = get_user_model().objects.create_user(
            username="person-attachment-uploader"
        )
        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )
        self.person = Person.objects.create(
            first_name="Ada",
            last_name="Nováková",
        )
        self.category = AttachmentCategory.objects.create(
            code="person-upload-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="person-upload-evidence",
            name="Doklad",
        )
        self.storage = ProtectedAttachmentStorage()

    def data(self, *, access_level=AccessLevel.AUTHENTICATED):
        return AttachmentUploadInput(
            category=self.category,
            original_filename="doklad.pdf",
            declared_mime_type="application/pdf",
            display_name="Rodinný doklad",
            description="Popis dokumentu",
            access_level=access_level,
        )

    def test_creates_owned_attachment_and_person_link_with_same_access(self):
        link = upload_person_attachment(
            actor=self.actor,
            person=self.person,
            data=self.data(),
            role=self.role,
            stream=SimpleUploadedFile(
                "doklad.pdf",
                self.pdf(),
                content_type="application/pdf",
            ),
            storage=self.storage,
        )

        attachment = link.attachment
        self.assertEqual(link.person, self.person)
        self.assertEqual(link.role, self.role)
        self.assertEqual(link.created_by, self.actor)
        self.assertEqual(link.access_level, AccessLevel.AUTHENTICATED)
        self.assertEqual(attachment.access_level, link.access_level)
        self.assertEqual(attachment.display_name, "Rodinný doklad")
        self.assertEqual(attachment.description, "Popis dokumentu")
        self.assertEqual(attachment.file_status, FileStatus.AVAILABLE)
        self.assertEqual(attachment.vault.owner, self.actor)

    def test_current_permission_and_person_state_are_checked_before_stream(self):
        stale_actor = get_user_model().objects.get(pk=self.actor.pk)
        self.actor.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            upload_person_attachment(
                actor=stale_actor,
                person=self.person,
                data=self.data(),
                role=self.role,
                stream=UnreadableStream(),
                storage=self.storage,
            )

        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )
        Person.objects.filter(pk=self.person.pk).update(
            archived_at=timezone.now()
        )
        with self.assertRaises(Person.DoesNotExist):
            upload_person_attachment(
                actor=self.actor,
                person=self.person,
                data=self.data(),
                role=self.role,
                stream=UnreadableStream(),
                storage=self.storage,
            )

        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(PersonAttachment.objects.count(), 0)

    def test_access_level_outside_actor_policy_is_denied_before_stream(self):
        with self.assertRaises(PermissionDenied):
            upload_person_attachment(
                actor=self.actor,
                person=self.person,
                data=self.data(access_level=AccessLevel.RESTRICTED),
                role=self.role,
                stream=UnreadableStream(),
                storage=self.storage,
            )

        self.assertEqual(Attachment.objects.count(), 0)

    def test_link_failure_rolls_back_database_and_deletes_new_blob(self):
        recording = RecordingStorage(self.storage)

        with (
            patch(
                "materials.upload_services.create_person_attachment",
                side_effect=RuntimeError("link failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "link failed"),
        ):
            upload_person_attachment(
                actor=self.actor,
                person=self.person,
                data=self.data(),
                role=self.role,
                stream=BytesIO(self.pdf()),
                storage=recording,
            )

        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(PersonAttachment.objects.count(), 0)
        self.assertEqual(recording.deletes, recording.writes)
        vault, storage_key = recording.writes[0]
        self.assertFalse(recording.exists(vault, storage_key))

    def test_cleanup_failure_does_not_mask_link_failure(self):
        recording = RecordingStorage(self.storage)

        with (
            patch(
                "materials.upload_services.create_person_attachment",
                side_effect=RuntimeError("original link failure"),
            ),
            patch.object(
                recording,
                "delete",
                side_effect=ProtectedStorageError("cleanup failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "original link failure"),
        ):
            upload_person_attachment(
                actor=self.actor,
                person=self.person,
                data=self.data(),
                role=self.role,
                stream=BytesIO(self.pdf()),
                storage=recording,
            )

        self.assertEqual(Attachment.objects.count(), 0)
        self.assertEqual(PersonAttachment.objects.count(), 0)

    @staticmethod
    def pdf() -> bytes:
        stream = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(stream)
        return stream.getvalue()
