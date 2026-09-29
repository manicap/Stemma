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
from .services import (
    restore_soft_deleted_health_record,
    soft_delete_health_record,
)


class HealthRecordSoftDeleteServiceTests(TestCase):
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
        self.inactive_type = HealthRecordType.objects.create(
            code="inactive",
            name="Neaktivní",
            is_active=False,
        )
        self.creator = get_user_model().objects.create_user(username="creator")
        self.actor = self.user(
            "deleter",
            "health.delete_healthrecord",
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

    def assert_error_code(self, context, code: str) -> None:
        self.assertEqual(
            context.exception.error_dict["health_record"][0].code,
            code,
        )

    def test_soft_delete_sets_metadata_and_preserves_business_data(self) -> None:
        record = self.record()
        old_updated_at = record.updated_at - timedelta(days=1)
        HealthRecord.objects.filter(pk=record.pk).update(
            updated_at=old_updated_at
        )

        result = soft_delete_health_record(
            health_record=record,
            person=self.person,
            actor=self.actor,
            reason="  Duplicitní záznam  ",
        )

        self.assertIsNotNone(result.deleted_at)
        self.assertEqual(result.deleted_by_id, self.actor.pk)
        self.assertEqual(result.deletion_reason, "Duplicitní záznam")
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
        self.assertIsNone(result.archived_at)
        with self.assertRaises(HealthRecord.DoesNotExist):
            get_visible_health_record(
                health_record_id=result.pk,
                actor=self.actor,
            )

    def test_restore_clears_delete_metadata_and_preserves_business_data(
        self,
    ) -> None:
        deleted = soft_delete_health_record(
            health_record=self.record(),
            person=self.person,
            actor=self.actor,
            reason="Důvod",
        )
        old_updated_at = deleted.updated_at - timedelta(days=1)
        HealthRecord.objects.filter(pk=deleted.pk).update(
            updated_at=old_updated_at
        )

        result = restore_soft_deleted_health_record(
            health_record=deleted,
            person=self.person,
            actor=self.actor,
        )

        self.assertIsNone(result.deleted_at)
        self.assertIsNone(result.deleted_by_id)
        self.assertEqual(result.deletion_reason, "")
        self.assertGreater(result.updated_at, old_updated_at)
        self.assertEqual(result.created_by_id, self.creator.pk)
        self.assertEqual(result.title, "Kontrola")
        self.assertEqual(
            get_visible_health_record(
                health_record_id=result.pk,
                actor=self.actor,
            ),
            result,
        )

    def test_soft_delete_requires_non_blank_reason_after_authorization(
        self,
    ) -> None:
        for reason in ("", " \t\n "):
            record = self.record(title=f"Důvod {reason!r}")
            with self.subTest(reason=reason):
                with self.assertRaises(ValidationError) as error:
                    soft_delete_health_record(
                        health_record=record,
                        person=self.person,
                        actor=self.actor,
                        reason=reason,
                    )
                self.assertEqual(
                    error.exception.error_dict["deletion_reason"][0].code,
                    "health_record_deletion_reason_required",
                )
                record.refresh_from_db()
                self.assertIsNone(record.deleted_at)

    def test_lifecycle_state_machine_returns_stable_codes(self) -> None:
        archived = self.record(
            title="Archivovaný",
            archived_at=timezone.now(),
        )
        deleted = self.record(
            title="Odstraněný",
            deleted_at=timezone.now(),
            deleted_by=self.actor,
            deletion_reason="Původní",
        )
        active = self.record(title="Aktivní")
        for record in (archived, deleted):
            with self.subTest(operation="soft_delete", record=record.pk):
                with self.assertRaises(ValidationError) as error:
                    soft_delete_health_record(
                        health_record=record,
                        person=self.person,
                        actor=self.actor,
                        reason="Nový",
                    )
                self.assert_error_code(error, "health_record_not_active")
        for record in (active, archived):
            with self.subTest(operation="restore", record=record.pk):
                with self.assertRaises(ValidationError) as error:
                    restore_soft_deleted_health_record(
                        health_record=record,
                        person=self.person,
                        actor=self.actor,
                    )
                self.assert_error_code(
                    error,
                    "health_record_not_soft_deleted",
                )

        deleted.refresh_from_db()
        self.assertEqual(deleted.deletion_reason, "Původní")
        self.assertIsNone(active.deleted_at)

    def test_combined_lifecycle_state_is_rejected_by_both_operations(
        self,
    ) -> None:
        combined = self.record(
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
            deletion_reason="Legacy",
        )
        operations = (
            (
                soft_delete_health_record,
                {"reason": "Nový důvod"},
            ),
            (restore_soft_deleted_health_record, {}),
        )
        for operation, extra in operations:
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(ValidationError) as error:
                    operation(
                        health_record=combined,
                        person=self.person,
                        actor=self.actor,
                        **extra,
                    )
                self.assert_error_code(
                    error,
                    "health_record_lifecycle_invalid",
                )

    def test_wrong_person_missing_and_unavailable_context_fail_closed(
        self,
    ) -> None:
        active = self.record(title="Aktivní skrytý")
        deleted = self.record(
            title="Odstraněný skrytý",
            deleted_at=timezone.now(),
            deletion_reason="Důvod",
        )
        missing = HealthRecord(pk=active.pk + deleted.pk + 1000)
        for record, person, operation, extra in (
            (active, self.other_person, soft_delete_health_record, {"reason": "X"}),
            (deleted, self.other_person, restore_soft_deleted_health_record, {}),
            (missing, self.person, soft_delete_health_record, {"reason": "X"}),
            (missing, self.person, restore_soft_deleted_health_record, {}),
        ):
            with self.subTest(operation=operation.__name__, record=record.pk):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    operation(
                        health_record=record,
                        person=person,
                        actor=self.actor,
                        **extra,
                    )

        for person_field in ("archived_at", "deleted_at"):
            person = Person.objects.create(first_name=person_field)
            active_record = self.record(person=person)
            deleted_record = self.record(
                person=person,
                deleted_at=timezone.now(),
                deletion_reason="Důvod",
            )
            Person.objects.filter(pk=person.pk).update(
                **{person_field: timezone.now()}
            )
            with self.subTest(person_field=person_field):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    soft_delete_health_record(
                        health_record=active_record,
                        person=person,
                        actor=self.actor,
                        reason="X",
                    )
                with self.assertRaises(HealthRecord.DoesNotExist):
                    restore_soft_deleted_health_record(
                        health_record=deleted_record,
                        person=person,
                        actor=self.actor,
                    )

        inactive_type_record = self.record(record_type=self.inactive_type)
        with self.assertRaises(HealthRecord.DoesNotExist):
            soft_delete_health_record(
                health_record=inactive_type_record,
                person=self.person,
                actor=self.actor,
                reason="X",
            )
        inactive_type_deleted = self.record(
            record_type=self.inactive_type,
            deleted_at=timezone.now(),
            deletion_reason="Důvod",
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            restore_soft_deleted_health_record(
                health_record=inactive_type_deleted,
                person=self.person,
                actor=self.actor,
            )

    def test_content_policy_staff_authorship_and_superuser_are_preserved(
        self,
    ) -> None:
        restricted_actor = self.user(
            "restricted",
            "health.delete_healthrecord",
            "accounts.view_restricted_content",
        )
        hidden = self.record(access_level=AccessLevel.ADMIN_ONLY)
        with self.assertRaises(HealthRecord.DoesNotExist):
            soft_delete_health_record(
                health_record=hidden,
                person=self.person,
                actor=restricted_actor,
                reason="",
            )
        hidden_deleted = self.record(
            access_level=AccessLevel.ADMIN_ONLY,
            deleted_at=timezone.now(),
            deletion_reason="Důvod",
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            restore_soft_deleted_health_record(
                health_record=hidden_deleted,
                person=self.person,
                actor=restricted_actor,
            )

        hidden_person = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_person_record = self.record(person=hidden_person)
        hidden_person_deleted = self.record(
            person=hidden_person,
            deleted_at=timezone.now(),
            deletion_reason="Důvod",
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            soft_delete_health_record(
                health_record=hidden_person_record,
                person=hidden_person,
                actor=restricted_actor,
                reason="X",
            )
        with self.assertRaises(HealthRecord.DoesNotExist):
            restore_soft_deleted_health_record(
                health_record=hidden_person_deleted,
                person=hidden_person,
                actor=restricted_actor,
            )

        staff = self.user(
            "staff",
            "health.delete_healthrecord",
            is_staff=True,
        )
        authored = self.record(created_by=staff)
        with self.assertRaises(HealthRecord.DoesNotExist):
            soft_delete_health_record(
                health_record=authored,
                person=self.person,
                actor=staff,
                reason="X",
            )

        superuser = self.user("root", is_superuser=True)
        deleted = soft_delete_health_record(
            health_record=hidden,
            person=self.person,
            actor=superuser,
            reason="Správa",
        )
        restored = restore_soft_deleted_health_record(
            health_record=deleted,
            person=self.person,
            actor=superuser,
        )
        self.assertIsNone(restored.deleted_at)

    def test_invalid_inactive_and_unprivileged_actors_are_denied(self) -> None:
        unsaved = get_user_model()(username="unsaved")
        inactive = self.user(
            "inactive",
            "health.delete_healthrecord",
            is_active=False,
        )
        no_permission = self.user("reader")
        active = self.record()
        deleted = self.record(
            deleted_at=timezone.now(),
            deletion_reason="Důvod",
        )
        for actor in (AnonymousUser(), unsaved, inactive, no_permission):
            with self.subTest(actor=type(actor).__name__):
                with self.assertRaises(PermissionDenied):
                    soft_delete_health_record(
                        health_record=active,
                        person=self.person,
                        actor=actor,
                        reason="X",
                    )
                with self.assertRaises(PermissionDenied):
                    restore_soft_deleted_health_record(
                        health_record=deleted,
                        person=self.person,
                        actor=actor,
                    )

    def test_authorization_precedes_target_and_reason_validation(self) -> None:
        with self.assertRaises(PermissionDenied):
            soft_delete_health_record(
                health_record=HealthRecord(),
                person=Person(),
                actor=AnonymousUser(),
                reason="",
            )
        with self.assertRaises(HealthRecord.DoesNotExist):
            soft_delete_health_record(
                health_record=HealthRecord(),
                person=Person(),
                actor=self.actor,
                reason="",
            )

    def test_fresh_permission_revocation_and_lock_recheck_are_enforced(
        self,
    ) -> None:
        revoked_target = self.record(title="Revoked")
        permission = Permission.objects.get(
            content_type__app_label="health",
            codename="delete_healthrecord",
        )
        self.actor.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            soft_delete_health_record(
                health_record=revoked_target,
                person=self.person,
                actor=self.actor,
                reason="X",
            )
        revoked_target.refresh_from_db()
        self.assertIsNone(revoked_target.deleted_at)

        self.actor.user_permissions.add(permission)
        current_actor = get_user_model().objects.get(pk=self.actor.pk)
        active = self.record(title="Recheck active")
        deleted = self.record(
            title="Recheck deleted",
            deleted_at=timezone.now(),
            deletion_reason="Původní",
        )
        for operation, record, extra in (
            (soft_delete_health_record, active, {"reason": "X"}),
            (restore_soft_deleted_health_record, deleted, {}),
        ):
            with self.subTest(operation=operation.__name__):
                with patch(
                    "health.services.require_active_actor_permission",
                    side_effect=(current_actor, PermissionDenied("revoked")),
                ) as permission_check:
                    with self.assertRaises(PermissionDenied):
                        operation(
                            health_record=record,
                            person=self.person,
                            actor=self.actor,
                            **extra,
                        )
                self.assertEqual(permission_check.call_count, 2)

    def test_operations_lock_and_use_fresh_target_state(self) -> None:
        stale_active = self.record()
        HealthRecord.objects.filter(pk=stale_active.pk).update(
            deleted_at=timezone.now(),
            deleted_by=self.actor,
            deletion_reason="Fresh",
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
            restored = restore_soft_deleted_health_record(
                health_record=stale_active,
                person=self.person,
                actor=self.actor,
            )

        record_lock.assert_called_once_with()
        person_lock.assert_called_once_with()
        type_lock.assert_called_once_with()
        self.assertIsNone(restored.deleted_at)

    def test_soft_delete_and_restore_roll_back_save_then_fail(self) -> None:
        active = self.record(title="Aktivní rollback")
        deleted = self.record(
            title="Odstraněný rollback",
            deleted_at=timezone.now(),
            deleted_by=self.actor,
            deletion_reason="Původní",
        )
        original_save = HealthRecord.save

        def save_then_fail(instance, *args, **kwargs) -> None:
            original_save(instance, *args, **kwargs)
            raise IntegrityError("chyba po lifecycle zápisu")

        operations = (
            (soft_delete_health_record, active, {"reason": "Nový"}),
            (restore_soft_deleted_health_record, deleted, {}),
        )
        for operation, record, extra in operations:
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
                            **extra,
                        )

        active.refresh_from_db()
        deleted.refresh_from_db()
        self.assertIsNone(active.deleted_at)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.deleted_by_id, self.actor.pk)
        self.assertEqual(deleted.deletion_reason, "Původní")

    def test_material_lifecycle_is_strictly_non_cascade(self) -> None:
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
        source_role = SourceRole.objects.create(code="source", name="Zdroj")
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
            (model, instance.pk): model.objects.get(pk=instance.pk).updated_at
            for model, instance in (
                (Attachment, attachment),
                (HealthRecordAttachment, attachment_link),
                (Source, source),
                (HealthRecordSource, source_link),
            )
        }

        deleted = soft_delete_health_record(
            health_record=record,
            person=self.person,
            actor=self.actor,
            reason="Duplicitní",
        )
        for selector in (
            get_visible_health_record_attachment_links,
            get_visible_health_record_source_links,
        ):
            with self.assertRaises(HealthRecord.DoesNotExist):
                list(selector(health_record=deleted, actor=self.actor))

        HealthRecordSource.objects.filter(pk=source_link.pk).update(
            deleted_at=timezone.now()
        )
        restored = restore_soft_deleted_health_record(
            health_record=deleted,
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
            [],
        )
        for model, instance in (
            (Attachment, attachment),
            (HealthRecordAttachment, attachment_link),
            (Source, source),
        ):
            current = model.objects.get(pk=instance.pk)
            self.assertEqual(
                current.updated_at,
                material_state[(model, instance.pk)],
            )
            self.assertIsNone(current.deleted_at)
        source_link.refresh_from_db()
        self.assertIsNotNone(source_link.deleted_at)
