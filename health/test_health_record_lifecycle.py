from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from materials.choices import FileStatus, SourceSupport
from materials.models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    HealthRecordAttachment,
    HealthRecordSource,
    Source,
    SourceRole,
    SourceType,
)
from materials.selectors import (
    get_visible_health_record_attachment_links,
    get_visible_health_record_source_links,
)
from people.models import Person

from .models import HealthRecord, HealthRecordType
from .selectors import get_visible_health_record
from .services import archive_health_record, restore_archived_health_record


class HealthRecordLifecycleServiceTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            access_level=AccessLevel.PUBLIC,
        )
        self.other_person = Person.objects.create(
            first_name="Berta",
            access_level=AccessLevel.PUBLIC,
        )
        self.record_type = HealthRecordType.objects.create(
            code="exam",
            name="Vyšetření",
        )
        self.creator = get_user_model().objects.create_user(username="creator")
        self.actor = self.user(
            "editor",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
            "accounts.view_admin_only_content",
        )

    def user(self, username: str, *permission_keys: str, **values: object):
        actor = get_user_model().objects.create_user(
            username=username,
            **values,
        )
        for permission_key in permission_keys:
            app_label, codename = permission_key.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        return actor

    def record(self, **changes: object) -> HealthRecord:
        values = {
            "person": self.person,
            "record_type": self.record_type,
            "title": "Kontrola",
            "description": "Popis",
            "provider_name": "Nemocnice",
            "note": "Poznámka",
            "access_level": AccessLevel.RESTRICTED,
            "verification_status": VerificationStatus.VERIFIED,
            "start_year": 2001,
            "created_by": self.creator,
        }
        values.update(changes)
        return HealthRecord.objects.create(**values)

    def assert_error_code(
        self,
        context,
        code: str,
    ) -> None:
        self.assertEqual(
            context.exception.error_dict["health_record"][0].code,
            code,
        )

    def test_archive_sets_metadata_and_preserves_business_data(self) -> None:
        record = self.record()
        old_updated_at = record.updated_at - timedelta(days=1)
        HealthRecord.objects.filter(pk=record.pk).update(
            updated_at=old_updated_at
        )

        result = archive_health_record(
            health_record=record,
            person=self.person,
            actor=self.actor,
            reason="  Uzavřená léčba  ",
        )

        self.assertIsNotNone(result.archived_at)
        self.assertEqual(result.archived_by_id, self.actor.pk)
        self.assertEqual(result.archive_reason, "Uzavřená léčba")
        self.assertGreater(result.updated_at, old_updated_at)
        self.assertEqual(result.created_by_id, self.creator.pk)
        self.assertEqual(result.person_id, self.person.pk)
        self.assertEqual(result.record_type_id, self.record_type.pk)
        self.assertEqual(result.title, "Kontrola")
        self.assertEqual(result.description, "Popis")
        self.assertEqual(result.provider_name, "Nemocnice")
        self.assertEqual(result.note, "Poznámka")
        self.assertEqual(result.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.start_year, 2001)
        self.assertIsNone(result.deleted_at)
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_visible_health_record(
                health_record_id=record.pk,
                actor=self.actor,
            )

    def test_archive_without_reason_uses_empty_value(self) -> None:
        result = archive_health_record(
            health_record=self.record(),
            person=self.person,
            actor=self.actor,
        )

        self.assertEqual(result.archive_reason, "")

    def test_restore_clears_archive_metadata_and_preserves_authorship(
        self,
    ) -> None:
        archived = archive_health_record(
            health_record=self.record(),
            person=self.person,
            actor=self.actor,
            reason="Důvod",
        )
        old_updated_at = archived.updated_at - timedelta(days=1)
        HealthRecord.objects.filter(pk=archived.pk).update(
            updated_at=old_updated_at
        )

        result = restore_archived_health_record(
            health_record=archived,
            person=self.person,
            actor=self.actor,
        )

        self.assertIsNone(result.archived_at)
        self.assertIsNone(result.archived_by_id)
        self.assertEqual(result.archive_reason, "")
        self.assertGreater(result.updated_at, old_updated_at)
        self.assertEqual(result.created_by_id, self.creator.pk)
        self.assertIsNone(result.deleted_at)
        self.assertEqual(
            get_visible_health_record(
                health_record_id=result.pk,
                actor=self.actor,
            ),
            result,
        )

    def test_non_idempotent_transitions_return_stable_codes(self) -> None:
        archived = archive_health_record(
            health_record=self.record(),
            person=self.person,
            actor=self.actor,
            reason="Ponechat",
        )
        with self.assertRaises(ValidationError) as archive_error:
            archive_health_record(
                health_record=archived,
                person=self.person,
                actor=self.actor,
                reason="Nepřepsat",
            )
        self.assert_error_code(archive_error, "health_record_not_active")

        active = self.record(title="Aktivní")
        with self.assertRaises(ValidationError) as restore_error:
            restore_archived_health_record(
                health_record=active,
                person=self.person,
                actor=self.actor,
            )
        self.assert_error_code(
            restore_error,
            "health_record_not_archived",
        )

        archived.refresh_from_db()
        active.refresh_from_db()
        self.assertEqual(archived.archive_reason, "Ponechat")
        self.assertIsNone(active.archived_at)

    def test_soft_deleted_and_combined_states_fail_closed(self) -> None:
        soft_deleted = self.record(title="Odstraněný")
        combined = self.record(
            title="Kombinovaný",
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        HealthRecord.objects.filter(pk=soft_deleted.pk).update(
            deleted_at=timezone.now()
        )

        for record in (soft_deleted, combined):
            for operation in (
                archive_health_record,
                restore_archived_health_record,
            ):
                with self.subTest(record=record.pk, operation=operation.__name__):
                    with self.assertRaises(HealthRecord.DoesNotExist):
                        operation(
                            health_record=record,
                            person=self.person,
                            actor=self.actor,
                        )

        soft_deleted.refresh_from_db()
        combined.refresh_from_db()
        self.assertIsNotNone(soft_deleted.deleted_at)
        self.assertIsNotNone(combined.archived_at)
        self.assertIsNotNone(combined.deleted_at)

    def test_person_context_and_lifecycle_fail_closed(self) -> None:
        wrong_person_record = self.record()
        archived_wrong_person_record = self.record(
            title="Archivovaný cizí",
            archived_at=timezone.now(),
        )
        for operation, record in (
            (archive_health_record, wrong_person_record),
            (restore_archived_health_record, archived_wrong_person_record),
        ):
            with self.subTest(operation=operation.__name__, context="wrong"):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    operation(
                        health_record=record,
                        person=self.other_person,
                        actor=self.actor,
                    )

        cases = (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"access_level": AccessLevel.ADMIN_ONLY},
        )
        restricted_actor = self.user(
            "restricted-editor",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
        )
        for index, person_change in enumerate(cases):
            person = Person.objects.create(first_name=f"Osoba {index}")
            active = self.record(person=person)
            archived = self.record(
                person=person,
                title=f"Archivovaný {index}",
                archived_at=timezone.now(),
            )
            Person.objects.filter(pk=person.pk).update(**person_change)
            actor = (
                restricted_actor
                if "access_level" in person_change
                else self.actor
            )
            with self.subTest(person_change=person_change):
                for operation, record in (
                    (archive_health_record, active),
                    (restore_archived_health_record, archived),
                ):
                    with self.assertRaises(HealthRecord.DoesNotExist):
                        operation(
                            health_record=record,
                            person=person,
                            actor=actor,
                        )

    def test_hidden_record_and_inactive_type_fail_closed(self) -> None:
        restricted_actor = self.user(
            "content-editor",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
        )
        hidden = self.record(access_level=AccessLevel.ADMIN_ONLY)
        archived_hidden = self.record(
            title="Archivovaný skrytý",
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=timezone.now(),
        )
        inactive_type = HealthRecordType.objects.create(
            code="inactive",
            name="Neaktivní",
            is_active=False,
        )
        inactive = self.record(
            title="Neaktivní typ",
            record_type=inactive_type,
        )
        archived_inactive = self.record(
            title="Archivovaný s neaktivním typem",
            record_type=inactive_type,
            archived_at=timezone.now(),
        )

        for operation, record, actor in (
            (archive_health_record, hidden, restricted_actor),
            (
                restore_archived_health_record,
                archived_hidden,
                restricted_actor,
            ),
            (archive_health_record, inactive, self.actor),
            (
                restore_archived_health_record,
                archived_inactive,
                self.actor,
            ),
        ):
            with self.subTest(operation=operation.__name__, record=record.pk):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    operation(
                        health_record=record,
                        person=self.person,
                        actor=actor,
                    )

    def test_physically_missing_target_fails_closed(self) -> None:
        missing = self.record()
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for operation in (
            archive_health_record,
            restore_archived_health_record,
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    operation(
                        health_record=missing,
                        person=self.person,
                        actor=self.actor,
                    )

    def test_actor_permission_matrix_and_authorship_do_not_bypass(self) -> None:
        no_permission = self.user(
            "no-permission",
            "accounts.view_restricted_content",
        )
        inactive = self.user(
            "inactive",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
            is_active=False,
        )
        staff = self.user(
            "staff",
            "health.change_healthrecord",
            is_staff=True,
        )
        unsaved = get_user_model()(username="unsaved")
        authored = self.record(created_by=no_permission)
        authored_archived = self.record(
            title="Archivovaný autorem",
            created_by=no_permission,
            archived_at=timezone.now(),
        )

        for actor in (
            AnonymousUser(),
            unsaved,
            no_permission,
            inactive,
        ):
            with self.subTest(actor=getattr(actor, "username", "anonymous")):
                for operation, record in (
                    (archive_health_record, authored),
                    (restore_archived_health_record, authored_archived),
                ):
                    with self.assertRaises(PermissionDenied):
                        operation(
                            health_record=record,
                            person=self.person,
                            actor=actor,
                        )

        authored.refresh_from_db()
        authored_archived.refresh_from_db()
        self.assertIsNone(authored.archived_at)
        self.assertIsNotNone(authored_archived.archived_at)

        for operation, record in (
            (archive_health_record, authored),
            (restore_archived_health_record, authored_archived),
        ):
            with self.assertRaises(HealthRecord.DoesNotExist):
                operation(
                    health_record=record,
                    person=self.person,
                    actor=staff,
                )

        superuser = self.user("superuser", is_superuser=True)
        archived = archive_health_record(
            health_record=authored,
            person=self.person,
            actor=superuser,
        )
        restored = restore_archived_health_record(
            health_record=archived,
            person=self.person,
            actor=superuser,
        )
        self.assertIsNone(restored.archived_at)

    def test_actor_authorization_precedes_target_validation(self) -> None:
        with self.assertRaises(PermissionDenied):
            archive_health_record(
                health_record=HealthRecord(),
                person=Person(),
                actor=AnonymousUser(),
            )
        with self.assertRaises(HealthRecord.DoesNotExist):
            archive_health_record(
                health_record=HealthRecord(),
                person=Person(),
                actor=self.actor,
            )

    def test_fresh_permission_revocation_is_enforced(self) -> None:
        record = self.record()
        self.actor.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="health",
                codename="change_healthrecord",
            )
        )

        with self.assertRaises(PermissionDenied):
            archive_health_record(
                health_record=record,
                person=self.person,
                actor=self.actor,
            )
        record.refresh_from_db()
        self.assertIsNone(record.archived_at)

    def test_permission_is_rechecked_after_lifecycle_locks(self) -> None:
        active = self.record()
        archived = self.record(
            title="Archivovaný recheck",
            archived_at=timezone.now(),
        )
        current_actor = get_user_model().objects.get(pk=self.actor.pk)
        for operation, record in (
            (archive_health_record, active),
            (restore_archived_health_record, archived),
        ):
            with self.subTest(operation=operation.__name__):
                with patch(
                    "health.services.require_active_actor_permission",
                    side_effect=(
                        current_actor,
                        PermissionDenied("revoked"),
                    ),
                ) as permission_check:
                    with self.assertRaises(PermissionDenied):
                        operation(
                            health_record=record,
                            person=self.person,
                            actor=self.actor,
                        )
                self.assertEqual(permission_check.call_count, 2)

        active.refresh_from_db()
        archived.refresh_from_db()
        self.assertIsNone(active.archived_at)
        self.assertIsNotNone(archived.archived_at)

    def test_lifecycle_operations_lock_and_use_fresh_target_state(self) -> None:
        stale_active = self.record()
        HealthRecord.objects.filter(pk=stale_active.pk).update(
            archived_at=timezone.now(),
            archive_reason="Fresh",
        )

        with (
            patch.object(
                HealthRecord.objects,
                "select_for_update",
                wraps=HealthRecord.objects.select_for_update,
            ) as record_lock,
            patch.object(
                Person.objects,
                "select_for_update",
                wraps=Person.objects.select_for_update,
            ) as person_lock,
            patch.object(
                HealthRecordType.objects,
                "select_for_update",
                wraps=HealthRecordType.objects.select_for_update,
            ) as type_lock,
        ):
            restored = restore_archived_health_record(
                health_record=stale_active,
                person=self.person,
                actor=self.actor,
            )

        record_lock.assert_called_once_with()
        person_lock.assert_called_once_with()
        type_lock.assert_called_once_with()
        self.assertIsNone(restored.archived_at)
        self.assertEqual(restored.archive_reason, "")

    def test_archive_and_restore_roll_back_save_then_fail(self) -> None:
        active = self.record(title="Aktivní rollback")
        archived = self.record(
            title="Archivovaný rollback",
            archived_at=timezone.now(),
            archived_by=self.actor,
            archive_reason="Původní",
        )
        original_save = HealthRecord.save

        def save_then_fail(instance, *args, **kwargs) -> None:
            original_save(instance, *args, **kwargs)
            raise IntegrityError("chyba po lifecycle zápisu")

        for operation, record in (
            (archive_health_record, active),
            (restore_archived_health_record, archived),
        ):
            with self.subTest(operation=operation.__name__):
                with patch.object(
                    HealthRecord,
                    "save",
                    autospec=True,
                    side_effect=save_then_fail,
                ):
                    with self.assertRaisesRegex(
                        IntegrityError,
                        "chyba po lifecycle zápisu",
                    ):
                        operation(
                            health_record=record,
                            person=self.person,
                            actor=self.actor,
                        )

        active.refresh_from_db()
        archived.refresh_from_db()
        self.assertIsNone(active.archived_at)
        self.assertIsNotNone(archived.archived_at)
        self.assertEqual(archived.archived_by_id, self.actor.pk)
        self.assertEqual(archived.archive_reason, "Původní")

    def test_attachment_and_source_lifecycle_is_strictly_non_cascade(
        self,
    ) -> None:
        record = self.record()
        category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        attachment_role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
        )
        attachment = Attachment.objects.create(
            category=category,
            original_filename="report.pdf",
            storage_key="health/report.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="a" * 64,
            file_status=FileStatus.AVAILABLE,
        )
        attachment_link = HealthRecordAttachment.objects.create(
            health_record=record,
            attachment=attachment,
            role=attachment_role,
        )
        source_type = SourceType.objects.create(code="archive", name="Archiv")
        source_role = SourceRole.objects.create(code="evidence", name="Doklad")
        source = Source.objects.create(
            source_type=source_type,
            title="Zdravotní dokumentace",
        )
        source_link = HealthRecordSource.objects.create(
            health_record=record,
            source=source,
            role=source_role,
            support_strength=SourceSupport.CONFIRMS,
        )
        material_state = {
            model: model.objects.get(pk=instance.pk).updated_at
            for model, instance in (
                (Attachment, attachment),
                (HealthRecordAttachment, attachment_link),
                (Source, source),
                (HealthRecordSource, source_link),
            )
        }

        archived = archive_health_record(
            health_record=record,
            person=self.person,
            actor=self.actor,
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            list(
                get_visible_health_record_attachment_links(
                    health_record=archived,
                    actor=self.actor,
                )
            )
        with self.assertRaises(HealthRecord.DoesNotExist):
            list(
                get_visible_health_record_source_links(
                    health_record=archived,
                    actor=self.actor,
                )
            )

        restored = restore_archived_health_record(
            health_record=archived,
            person=self.person,
            actor=self.actor,
        )
        self.assertEqual(
            list(
                get_visible_health_record_attachment_links(
                    health_record=restored,
                    actor=self.actor,
                )
            ),
            [attachment_link],
        )
        self.assertEqual(
            list(
                get_visible_health_record_source_links(
                    health_record=restored,
                    actor=self.actor,
                )
            ),
            [source_link],
        )
        for model, instance in (
            (Attachment, attachment),
            (HealthRecordAttachment, attachment_link),
            (Source, source),
            (HealthRecordSource, source_link),
        ):
            current = model.objects.get(pk=instance.pk)
            self.assertEqual(current.updated_at, material_state[model])
            self.assertIsNone(current.archived_at)
            self.assertIsNone(current.deleted_at)
