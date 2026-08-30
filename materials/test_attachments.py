from importlib import import_module

from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import (
    IntegrityError,
    connection,
    migrations,
    models,
    transaction,
)
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
)

from .choices import FileStatus
from .models import Attachment, AttachmentCategory


class FileStatusTests(SimpleTestCase):
    def test_members_values_labels_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(FileStatus),
            (
                FileStatus.PENDING,
                FileStatus.AVAILABLE,
                FileStatus.MISSING,
                FileStatus.QUARANTINED,
            ),
        )
        self.assertEqual(
            FileStatus.values,
            ["pending", "available", "missing", "quarantined"],
        )
        self.assertEqual(
            FileStatus.labels,
            [
                "Čeká na potvrzení",
                "Dostupný",
                "Nedostupný",
                "V karanténě",
            ],
        )

    def test_is_fixed_text_choices_without_database_table(self) -> None:
        self.assertTrue(issubclass(FileStatus, models.TextChoices))
        self.assertFalse(issubclass(FileStatus, models.Model))


class AttachmentModelTests(TestCase):
    sha256 = "a" * 64

    def setUp(self) -> None:
        self.category = AttachmentCategory.objects.create(
            code="test_document",
            name="Testovací dokument",
        )

    def attachment(self, **overrides) -> Attachment:
        values = {
            "category": self.category,
            "original_filename": "scan.pdf",
            "storage_key": "attachments/test/scan.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 123,
            "sha256": self.sha256,
        }
        values.update(overrides)
        return Attachment(**values)

    def test_inheritance_fields_and_metadata_are_exact(self) -> None:
        self.assertEqual(
            Attachment.__bases__,
            (
                TimestampedModel,
                PartialDateModel,
                AccessControlledModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertFalse(hasattr(Attachment(), "verification_status"))
        self.assertEqual(Attachment._meta.verbose_name, "Příloha")
        self.assertEqual(Attachment._meta.verbose_name_plural, "Přílohy")

        category = Attachment._meta.get_field("category")
        self.assertIs(category.remote_field.model, AttachmentCategory)
        self.assertIs(category.remote_field.on_delete, models.PROTECT)
        self.assertEqual(category.remote_field.related_name, "attachments")

        storage_key = Attachment._meta.get_field("storage_key")
        self.assertTrue(storage_key.unique)
        sha256 = Attachment._meta.get_field("sha256")
        self.assertTrue(sha256.db_index)
        self.assertFalse(sha256.unique)
        self.assertTrue(Attachment._meta.get_field("file_status").db_index)
        self.assertEqual(
            Attachment._meta.get_field("technical_metadata").default,
            dict,
        )

    def test_defaults_are_pending_public_and_independent(self) -> None:
        attachment = self.attachment()

        self.assertEqual(attachment.file_status, FileStatus.PENDING)
        self.assertEqual(attachment.access_level, "public")
        self.assertIsNone(attachment.archived_at)
        self.assertIsNone(attachment.deleted_at)

    def test_validates_sha256_and_json_object(self) -> None:
        for invalid_hash in ("a" * 63, "A" * 64, "z" * 64):
            with self.subTest(sha256=invalid_hash):
                with self.assertRaises(ValidationError) as context:
                    self.attachment(sha256=invalid_hash).full_clean()
                self.assertEqual(
                    context.exception.error_dict["sha256"][0].code,
                    "invalid_sha256",
                )

        with self.assertRaises(ValidationError) as context:
            self.attachment(technical_metadata=[]).full_clean()
        self.assertEqual(
            context.exception.error_dict["technical_metadata"][0].code,
            "technical_metadata_not_object",
        )

        with self.assertRaises(ValidationError) as context:
            self.attachment(file_status="unsafe_unknown").full_clean()
        self.assertEqual(
            context.exception.error_dict["file_status"][0].code,
            "invalid_choice",
        )

    def test_sha256_is_not_identity_but_storage_key_is_unique(self) -> None:
        first = self.attachment()
        first.full_clean()
        first.save()
        second = self.attachment(
            storage_key="attachments/test/copy.pdf",
        )
        second.full_clean()
        second.save()
        self.assertEqual(
            Attachment.objects.filter(sha256=self.sha256).count(),
            2,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.attachment().save()

    def test_file_status_does_not_change_lifecycle(self) -> None:
        archived_at = timezone.now()
        attachment = self.attachment(
            file_status=FileStatus.MISSING,
            archived_at=archived_at,
        )
        attachment.full_clean()
        attachment.save()

        attachment.file_status = FileStatus.QUARANTINED
        attachment.save(update_fields={"file_status"})
        attachment.refresh_from_db()

        self.assertEqual(attachment.file_status, FileStatus.QUARANTINED)
        self.assertEqual(attachment.archived_at, archived_at)
        self.assertIsNone(attachment.deleted_at)

    def test_database_enforces_size_and_protects_category(self) -> None:
        attachment = self.attachment()
        attachment.save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.attachment(
                    storage_key="attachments/test/negative",
                    size_bytes=-1,
                ).save()

        with self.assertRaises(ProtectedError):
            self.category.delete()
        self.assertTrue(Attachment.objects.filter(pk=attachment.pk).exists())

    def test_technical_metadata_default_is_not_shared(self) -> None:
        first = self.attachment(storage_key="attachments/first")
        second = self.attachment(storage_key="attachments/second")

        first.technical_metadata["pages"] = 2

        self.assertEqual(second.technical_metadata, {})

    def test_string_representation_uses_safe_fallbacks(self) -> None:
        self.assertEqual(
            str(self.attachment(display_name="  Matrika  ")),
            "Matrika",
        )
        self.assertEqual(str(self.attachment()), "scan.pdf")
        self.assertEqual(
            str(self.attachment(original_filename="")),
            "attachments/test/scan.pdf",
        )

    def test_table_exists_and_model_is_not_registered_in_admin(self) -> None:
        self.assertIn(
            Attachment._meta.db_table,
            connection.introspection.table_names(),
        )
        self.assertFalse(admin.site.is_registered(Attachment))


class AttachmentMigrationTests(SimpleTestCase):
    migration = import_module("materials.migrations.0002_attachments")

    def test_migration_is_single_attachment_model_after_lookups(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("materials", "0001_attachment_lookups"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "Attachment")
