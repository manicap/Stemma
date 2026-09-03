from importlib import import_module
from inspect import Parameter, signature
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import connection, migrations, models
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from health.models import HealthRecord, HealthRecordType
from health.permissions import get_health_record_visibility_filter
from people.models import Person
from places.models import Place

from . import selectors, services
from .choices import FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentLinkModel,
    AttachmentRole,
    HealthRecordAttachment,
)
from .selectors import get_visible_health_record_attachment_links
from .services import (
    AttachmentLinkInput,
    create_health_record_attachment,
    update_health_record_attachment,
)


class HealthRecordAttachmentApiTests(SimpleTestCase):
    def test_model_and_public_contract_follow_attachment_conventions(self) -> None:
        self.assertEqual(HealthRecordAttachment.__bases__, (AttachmentLinkModel,))
        health_record = HealthRecordAttachment._meta.get_field("health_record")
        attachment = HealthRecordAttachment._meta.get_field("attachment")
        self.assertIs(health_record.remote_field.model, HealthRecord)
        self.assertIs(health_record.remote_field.on_delete, models.PROTECT)
        self.assertEqual(health_record.remote_field.related_name, "attachment_links")
        self.assertIs(attachment.remote_field.model, Attachment)
        self.assertIs(attachment.remote_field.on_delete, models.PROTECT)
        self.assertEqual(
            attachment.remote_field.related_name,
            "health_record_links",
        )
        self.assertFalse(admin.site.is_registered(HealthRecordAttachment))

        expectations = (
            (
                create_health_record_attachment,
                ("health_record", "data", "created_by"),
            ),
            (
                update_health_record_attachment,
                ("link", "health_record", "data"),
            ),
            (
                get_visible_health_record_attachment_links,
                ("health_record", "actor"),
            ),
        )
        for callable_object, names in expectations:
            with self.subTest(callable=callable_object.__name__):
                parameters = signature(callable_object).parameters
                self.assertEqual(tuple(parameters), names)
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in parameters.values()
                    )
                )

    def test_no_general_attachment_or_link_id_read_api_is_exposed(self) -> None:
        self.assertIn(
            "get_visible_health_record_attachment_links",
            selectors.__all__,
        )
        self.assertNotIn("get_visible_attachment", selectors.__all__)
        self.assertNotIn(
            "get_visible_health_record_attachment_link",
            selectors.__all__,
        )
        self.assertIn("create_health_record_attachment", services.__all__)
        self.assertIn("update_health_record_attachment", services.__all__)


class HealthRecordAttachmentServiceTests(TestCase):
    sha256 = "c" * 64

    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Anna")
        self.record_type = HealthRecordType.objects.create(
            code="test",
            name="Test",
        )
        self.health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Záznam",
        )
        self.category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
        )
        self.attachment = Attachment.objects.create(
            category=self.category,
            original_filename="record.pdf",
            storage_key="health/record.pdf",
            mime_type="application/pdf",
            size_bytes=100,
            sha256=self.sha256,
        )

    def data(self, **changes: object) -> AttachmentLinkInput:
        values = {
            "attachment": self.attachment,
            "role": self.role,
            "context_description": "  Lékařská zpráva  ",
            "access_level": AccessLevel.RESTRICTED,
        }
        values.update(changes)
        return AttachmentLinkInput(**values)

    def test_create_and_update_use_existing_generic_link_service(self) -> None:
        link = create_health_record_attachment(
            health_record=self.health_record,
            data=self.data(),
        )
        self.assertIsInstance(link, HealthRecordAttachment)
        self.assertEqual(link.health_record, self.health_record)
        self.assertEqual(link.attachment, self.attachment)
        self.assertEqual(link.context_description, "Lékařská zpráva")

        updated = update_health_record_attachment(
            link=link,
            health_record=self.health_record,
            data=self.data(context_description="  Aktualizováno  "),
        )
        self.assertEqual(updated.pk, link.pk)
        self.assertEqual(updated.context_description, "Aktualizováno")

    def test_create_rejects_archived_or_deleted_endpoints(self) -> None:
        now = timezone.now()
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=now
        )
        with self.assertRaises(ValidationError) as archived_error:
            create_health_record_attachment(
                health_record=self.health_record,
                data=self.data(),
            )
        self.assertEqual(
            archived_error.exception.error_dict["health_record"][0].code,
            "health_record_archived",
        )

        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=None,
            deleted_at=now,
        )
        with self.assertRaises(ValidationError) as deleted_error:
            create_health_record_attachment(
                health_record=self.health_record,
                data=self.data(),
            )
        self.assertEqual(
            deleted_error.exception.error_dict["health_record"][0].code,
            "health_record_deleted",
        )

    def test_update_preserves_only_same_archived_target_and_active_link(
        self,
    ) -> None:
        link = create_health_record_attachment(
            health_record=self.health_record,
            data=self.data(),
        )
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=timezone.now()
        )
        preserved = update_health_record_attachment(
            link=link,
            health_record=self.health_record,
            data=self.data(context_description="Zachováno"),
        )
        self.assertEqual(preserved.health_record_id, self.health_record.pk)

        other_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Jiný archivovaný záznam",
            archived_at=timezone.now(),
        )
        with self.assertRaises(ValidationError) as archived_error:
            update_health_record_attachment(
                link=link,
                health_record=other_record,
                data=self.data(),
            )
        self.assertEqual(
            archived_error.exception.error_dict["health_record"][0].code,
            "health_record_archived",
        )

        HealthRecordAttachment.objects.filter(pk=link.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(ValidationError) as deleted_link_error:
            update_health_record_attachment(
                link=link,
                health_record=self.health_record,
                data=self.data(),
            )
        self.assertEqual(
            deleted_link_error.exception.error_dict["link"][0].code,
            "attachment_link_deleted",
        )


class HealthRecordAttachmentSelectorTests(TestCase):
    sha256 = "d" * 64

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            access_level=AccessLevel.PUBLIC,
        )
        self.record_type = HealthRecordType.objects.create(
            code="active",
            name="Aktivní",
        )
        self.health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Zdravotní záznam",
            access_level=AccessLevel.RESTRICTED,
        )
        self.category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
        )
        self.actor = self.create_user("reader", "view_restricted_content")

    def create_user(self, username: str, *codenames: str, **values: object):
        actor = get_user_model().objects.create_user(username=username, **values)
        for codename in codenames:
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="accounts",
                    content_type__model="user",
                    codename=codename,
                )
            )
        return actor

    def attachment(self, key: str, **changes: object) -> Attachment:
        values = {
            "category": self.category,
            "original_filename": f"{key}.pdf",
            "storage_key": f"health/{key}.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "sha256": self.sha256,
            "file_status": FileStatus.AVAILABLE,
        }
        values.update(changes)
        return Attachment.objects.create(**values)

    def link(
        self,
        key: str,
        *,
        health_record: HealthRecord | None = None,
        **changes: object,
    ) -> HealthRecordAttachment:
        attachment = changes.pop("attachment", None) or self.attachment(key)
        values = {
            "health_record": health_record or self.health_record,
            "attachment": attachment,
            "role": self.role,
        }
        values.update(changes)
        return HealthRecordAttachment.objects.create(**values)

    def visible(
        self,
        *,
        health_record: HealthRecord | None = None,
        actor=None,
    ) -> QuerySet[HealthRecordAttachment]:
        return get_visible_health_record_attachment_links(
            health_record=health_record or self.health_record,
            actor=self.actor if actor is None else actor,
        )

    def test_available_attachment_of_available_record_is_returned(self) -> None:
        available = self.link("available")

        result = self.visible()

        self.assertIsInstance(result, QuerySet)
        self.assertEqual(list(result), [available])

    def test_person_and_health_record_access_use_health_policy(self) -> None:
        visible = self.link("visible")
        with patch(
            "materials.selectors.get_health_record_visibility_filter",
            wraps=get_health_record_visibility_filter,
        ) as health_policy:
            self.assertEqual(list(self.visible()), [visible])
        self.assertEqual(health_policy.call_count, 1)

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible()

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.PUBLIC
        )
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible()

    def test_person_lifecycle_is_fail_closed_even_for_superuser(self) -> None:
        self.link("person-lifecycle")
        superuser = self.create_user("superuser", is_superuser=True)
        for field in ("archived_at", "deleted_at"):
            Person.objects.filter(pk=self.person.pk).update(
                archived_at=None,
                deleted_at=None,
            )
            Person.objects.filter(pk=self.person.pk).update(
                **{field: timezone.now()}
            )
            with self.subTest(field=field):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    self.visible(actor=superuser)

    def test_record_lifecycle_and_inactive_type_are_fail_closed(self) -> None:
        self.link("record-lifecycle")
        for field in ("archived_at", "deleted_at"):
            HealthRecord.objects.filter(pk=self.health_record.pk).update(
                archived_at=None,
                deleted_at=None,
            )
            HealthRecord.objects.filter(pk=self.health_record.pk).update(
                **{field: timezone.now()}
            )
            with self.subTest(field=field):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    self.visible()

        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            archived_at=None,
            deleted_at=None,
        )
        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible()

    def test_link_and_attachment_must_be_visible_and_active(self) -> None:
        available = self.link("available")
        self.link("archived-link", archived_at=timezone.now())
        self.link("deleted-link", deleted_at=timezone.now())
        self.link("hidden-link", access_level=AccessLevel.ADMIN_ONLY)
        self.link(
            "archived-file",
            attachment=self.attachment(
                "archived-attachment",
                archived_at=timezone.now(),
            ),
        )
        self.link(
            "deleted-file",
            attachment=self.attachment(
                "deleted-attachment",
                deleted_at=timezone.now(),
            ),
        )
        self.link(
            "hidden-file",
            attachment=self.attachment(
                "hidden-attachment",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )

        self.assertEqual(list(self.visible()), [available])

    def test_only_available_file_status_is_returned(self) -> None:
        available = self.link("available")
        for status in (
            FileStatus.PENDING,
            FileStatus.MISSING,
            FileStatus.QUARANTINED,
        ):
            self.link(
                status,
                attachment=self.attachment(
                    f"file-{status}",
                    file_status=status,
                ),
            )

        self.assertEqual(list(self.visible()), [available])

    def test_known_attachment_and_link_ids_cannot_bypass_health_policy(self) -> None:
        hidden_record = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Skrytý",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        hidden_link = self.link("known-hidden", health_record=hidden_record)
        known_attachment_id = hidden_link.attachment_id
        known_link_id = hidden_link.pk

        self.assertIsNotNone(known_attachment_id)
        self.assertIsNotNone(known_link_id)
        with self.assertRaises(HealthRecord.DoesNotExist):
            self.visible(health_record=hidden_record)
        self.assertEqual(list(self.visible().filter(pk=known_link_id)), [])
        self.assertNotIn("get_visible_attachment", selectors.__all__)
        self.assertNotIn(
            "get_visible_health_record_attachment_link",
            selectors.__all__,
        )

    def test_selector_matches_existing_attachment_delivery_boundaries(self) -> None:
        visible = self.link("visible")
        AttachmentRole.objects.filter(pk=self.role.pk).update(is_active=False)
        AttachmentCategory.objects.filter(pk=self.category.pk).update(
            is_active=False
        )

        self.assertEqual(list(self.visible()), [visible])

        HealthRecordAttachment.objects.filter(pk=visible.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(list(self.visible()), [])

    def test_lazy_result_rechecks_every_visibility_layer_in_database(self) -> None:
        def mutate_person_access(person, record_type, record, link, attachment):
            Person.objects.filter(pk=person.pk).update(
                access_level=AccessLevel.ADMIN_ONLY
            )

        def mutate_person_archived(person, record_type, record, link, attachment):
            Person.objects.filter(pk=person.pk).update(archived_at=timezone.now())

        def mutate_person_deleted(person, record_type, record, link, attachment):
            Person.objects.filter(pk=person.pk).update(deleted_at=timezone.now())

        def mutate_record_access(person, record_type, record, link, attachment):
            HealthRecord.objects.filter(pk=record.pk).update(
                access_level=AccessLevel.ADMIN_ONLY
            )

        def mutate_record_archived(person, record_type, record, link, attachment):
            HealthRecord.objects.filter(pk=record.pk).update(
                archived_at=timezone.now()
            )

        def mutate_record_deleted(person, record_type, record, link, attachment):
            HealthRecord.objects.filter(pk=record.pk).update(
                deleted_at=timezone.now()
            )

        def mutate_type(person, record_type, record, link, attachment):
            HealthRecordType.objects.filter(pk=record_type.pk).update(
                is_active=False
            )

        def mutate_link_access(person, record_type, record, link, attachment):
            HealthRecordAttachment.objects.filter(pk=link.pk).update(
                access_level=AccessLevel.ADMIN_ONLY
            )

        def mutate_link_archived(person, record_type, record, link, attachment):
            HealthRecordAttachment.objects.filter(pk=link.pk).update(
                archived_at=timezone.now()
            )

        def mutate_link_deleted(person, record_type, record, link, attachment):
            HealthRecordAttachment.objects.filter(pk=link.pk).update(
                deleted_at=timezone.now()
            )

        def mutate_attachment_access(
            person, record_type, record, link, attachment
        ):
            Attachment.objects.filter(pk=attachment.pk).update(
                access_level=AccessLevel.ADMIN_ONLY
            )

        def mutate_attachment_archived(
            person, record_type, record, link, attachment
        ):
            Attachment.objects.filter(pk=attachment.pk).update(
                archived_at=timezone.now()
            )

        def mutate_attachment_deleted(
            person, record_type, record, link, attachment
        ):
            Attachment.objects.filter(pk=attachment.pk).update(
                deleted_at=timezone.now()
            )

        def mutate_file_status(person, record_type, record, link, attachment):
            Attachment.objects.filter(pk=attachment.pk).update(
                file_status=FileStatus.MISSING
            )

        mutations = (
            mutate_person_access,
            mutate_person_archived,
            mutate_person_deleted,
            mutate_record_access,
            mutate_record_archived,
            mutate_record_deleted,
            mutate_type,
            mutate_link_access,
            mutate_link_archived,
            mutate_link_deleted,
            mutate_attachment_access,
            mutate_attachment_archived,
            mutate_attachment_deleted,
            mutate_file_status,
        )
        for index, mutate in enumerate(mutations):
            person = Person.objects.create(first_name=f"Fresh {index}")
            record_type = HealthRecordType.objects.create(
                code=f"fresh-{index}",
                name=f"Fresh {index}",
            )
            record = HealthRecord.objects.create(
                person=person,
                record_type=record_type,
                title=f"Fresh {index}",
            )
            attachment = self.attachment(f"fresh-{index}")
            link = HealthRecordAttachment.objects.create(
                health_record=record,
                attachment=attachment,
                role=self.role,
            )
            queryset = self.visible(health_record=record)

            mutate(person, record_type, record, link, attachment)

            with self.subTest(mutation=mutate.__name__):
                self.assertEqual(list(queryset), [])

    def test_result_is_preloaded_without_storage_access_or_n_plus_one(self) -> None:
        link_author = self.create_user("link-author")
        record_author = self.create_user("record-author")
        attachment_author = self.create_user("attachment-author")
        place = Place.objects.create(name="Praha", normalized_name="praha")
        HealthRecord.objects.filter(pk=self.health_record.pk).update(
            place=place,
            created_by=record_author,
        )
        later = self.link(
            "later",
            sort_order=20,
            created_by=link_author,
            attachment=self.attachment(
                "later-authored",
                created_by=attachment_author,
            ),
        )
        earlier = self.link(
            "earlier",
            sort_order=10,
            created_by=link_author,
            attachment=self.attachment(
                "earlier-authored",
                created_by=attachment_author,
            ),
        )
        queryset = self.visible()

        with (
            patch.object(default_storage, "open") as storage_open,
            patch.object(default_storage, "url") as storage_url,
            CaptureQueriesContext(connection) as queries,
        ):
            result = list(queryset)
            for link in result:
                str(link.health_record.person)
                str(link.health_record.record_type)
                link.health_record.place
                link.health_record.created_by
                str(link.attachment.category)
                link.attachment.created_by
                str(link.role)
                link.created_by

        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(queries), 1)
        storage_open.assert_not_called()
        storage_url.assert_not_called()

    def test_invalid_record_and_actor_keep_stable_central_errors(self) -> None:
        with self.assertRaises(ValidationError) as invalid_record:
            get_visible_health_record_attachment_links(
                health_record=HealthRecord(),
                actor=self.actor,
            )
        self.assertEqual(
            invalid_record.exception.error_dict["health_record"][0].code,
            "health_record_unsaved",
        )

        missing = HealthRecord.objects.create(
            person=self.person,
            record_type=self.record_type,
            title="Fyzicky chybějící",
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        with self.assertRaises(ValidationError) as missing_record:
            get_visible_health_record_attachment_links(
                health_record=missing,
                actor=self.actor,
            )
        self.assertEqual(
            missing_record.exception.error_dict["health_record"][0].code,
            "health_record_unsaved",
        )

        with self.assertRaises(ValidationError) as invalid_actor:
            get_visible_health_record_attachment_links(
                health_record=self.health_record,
                actor=None,
            )
        self.assertEqual(
            invalid_actor.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )


class HealthRecordAttachmentMigrationTests(TestCase):
    migration = import_module(
        "materials.migrations.0007_health_record_attachment"
    )

    def test_migration_is_single_structural_model_addition(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("health", "0002_health_records"),
                ("materials", "0006_source_links"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "HealthRecordAttachment")

    def test_table_exists(self) -> None:
        self.assertIn(
            HealthRecordAttachment._meta.db_table,
            connection.introspection.table_names(),
        )
