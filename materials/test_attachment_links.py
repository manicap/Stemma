from importlib import import_module
from unittest.mock import patch

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
    TimestampedModel,
)
from events.models import Event, EventType
from people.models import Person, Relationship, RelationshipType
from places.models import (
    GraveSite,
    GraveSiteType,
    Place,
    Residence,
    ResidenceType,
)

from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentLinkModel,
    AttachmentRole,
    EventAttachment,
    GraveSiteAttachment,
    PersonAttachment,
    PlaceAttachment,
    RelationshipAttachment,
    ResidenceAttachment,
)
from .services import (
    AttachmentLinkInput,
    create_event_attachment,
    create_grave_site_attachment,
    create_person_attachment,
    create_place_attachment,
    create_relationship_attachment,
    create_residence_attachment,
    update_person_attachment,
    update_event_attachment,
    update_grave_site_attachment,
    update_place_attachment,
    update_relationship_attachment,
    update_residence_attachment,
)


LINK_MODELS = (
    PersonAttachment,
    EventAttachment,
    RelationshipAttachment,
    ResidenceAttachment,
    GraveSiteAttachment,
    PlaceAttachment,
)


class AttachmentLinkStructureTests(SimpleTestCase):
    def test_abstract_base_has_exact_policy_and_business_fields(self) -> None:
        self.assertTrue(AttachmentLinkModel._meta.abstract)
        self.assertEqual(
            AttachmentLinkModel.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertEqual(
            {
                field.name
                for field in AttachmentLinkModel._meta.local_fields
            },
            {
                "created_at",
                "updated_at",
                "access_level",
                "created_by",
                "archived_at",
                "archived_by",
                "archive_reason",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
                "role",
                "context_description",
                "sort_order",
                "is_primary",
            },
        )

    def test_six_concrete_models_have_exact_targets_and_protection(self) -> None:
        specifications = (
            (PersonAttachment, "person", Person, "person_links"),
            (EventAttachment, "event", Event, "event_links"),
            (
                RelationshipAttachment,
                "relationship",
                Relationship,
                "relationship_links",
            ),
            (
                ResidenceAttachment,
                "residence",
                Residence,
                "residence_links",
            ),
            (
                GraveSiteAttachment,
                "grave_site",
                GraveSite,
                "grave_site_links",
            ),
            (PlaceAttachment, "place", Place, "place_links"),
        )

        for model, target_name, target_model, attachment_reverse in (
            specifications
        ):
            with self.subTest(model=model.__name__):
                self.assertEqual(model.__bases__, (AttachmentLinkModel,))
                target = model._meta.get_field(target_name)
                attachment = model._meta.get_field("attachment")
                role = model._meta.get_field("role")
                self.assertIs(target.remote_field.model, target_model)
                self.assertIs(target.remote_field.on_delete, models.PROTECT)
                self.assertEqual(
                    target.remote_field.related_name,
                    "attachment_links",
                )
                self.assertIs(attachment.remote_field.model, Attachment)
                self.assertIs(
                    attachment.remote_field.on_delete,
                    models.PROTECT,
                )
                self.assertEqual(
                    attachment.remote_field.related_name,
                    attachment_reverse,
                )
                self.assertIs(role.remote_field.model, AttachmentRole)
                self.assertIs(role.remote_field.on_delete, models.PROTECT)
                self.assertFalse(admin.site.is_registered(model))

    def test_defaults_do_not_invent_photo_semantics(self) -> None:
        for model in LINK_MODELS:
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    model._meta.get_field("context_description").default,
                    models.NOT_PROVIDED,
                )
                self.assertEqual(
                    model._meta.get_field("sort_order").default,
                    0,
                )
                self.assertFalse(
                    model._meta.get_field("is_primary").default
                )


class AttachmentLinkServiceTests(TestCase):
    def setUp(self) -> None:
        self.category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
        )
        self.attachment = self.make_attachment("one")
        self.person = Person.objects.create(first_name="Anna")
        self.other_person = Person.objects.create(first_name="Berta")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.other_place = Place.objects.create(
            name="Brno",
            normalized_name="brno",
        )
        self.event_type = EventType.objects.create(
            code="test_event",
            name="Testovací událost",
        )
        self.event = Event.objects.create(event_type=self.event_type)
        self.relationship_type = RelationshipType.objects.create(
            code="test_relationship",
            name="Testovací vazba",
            forward_label_male="vazba",
            forward_label_female="vazba",
            forward_label_unknown="vazba",
            reverse_label_male="vazba",
            reverse_label_female="vazba",
            reverse_label_unknown="vazba",
            is_symmetric=True,
        )
        self.relationship = Relationship.objects.create(
            relationship_type=self.relationship_type,
            person_a=self.person,
            person_b=self.other_person,
        )
        self.residence_type = ResidenceType.objects.create(
            code="test_residence",
            name="Testovací bydliště",
        )
        self.residence = Residence.objects.create(
            person=self.person,
            residence_type=self.residence_type,
            place=self.place,
        )
        self.grave_site_type = GraveSiteType.objects.create(
            code="test_grave",
            name="Testovací hrob",
        )
        self.grave_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            location_text="Testovací místo",
        )

    def make_attachment(self, suffix: str) -> Attachment:
        return Attachment.objects.create(
            category=self.category,
            original_filename=f"{suffix}.pdf",
            storage_key=f"attachments/{suffix}",
            mime_type="application/pdf",
            size_bytes=1,
            sha256=(suffix[0] if suffix[0] in "abcdef" else "a") * 64,
        )

    def data(self, **overrides) -> AttachmentLinkInput:
        values = {
            "attachment": self.attachment,
            "role": self.role,
            "context_description": "  Kontext  ",
            "sort_order": 7,
        }
        values.update(overrides)
        return AttachmentLinkInput(**values)

    def assert_error_code(
        self,
        exception: ValidationError,
        field: str,
        code: str,
    ) -> None:
        self.assertEqual(exception.error_dict[field][0].code, code)

    def test_create_services_cover_all_six_explicit_targets(self) -> None:
        cases = (
            (
                create_person_attachment,
                {"person": self.person},
                PersonAttachment,
                "person",
                self.person,
            ),
            (
                create_event_attachment,
                {"event": self.event},
                EventAttachment,
                "event",
                self.event,
            ),
            (
                create_relationship_attachment,
                {"relationship": self.relationship},
                RelationshipAttachment,
                "relationship",
                self.relationship,
            ),
            (
                create_residence_attachment,
                {"residence": self.residence},
                ResidenceAttachment,
                "residence",
                self.residence,
            ),
            (
                create_grave_site_attachment,
                {"grave_site": self.grave_site},
                GraveSiteAttachment,
                "grave_site",
                self.grave_site,
            ),
            (
                create_place_attachment,
                {"place": self.place},
                PlaceAttachment,
                "place",
                self.place,
            ),
        )

        for service, arguments, model, target_field, target in cases:
            with self.subTest(model=model.__name__):
                link = service(data=self.data(), **arguments)
                self.assertIsInstance(link, model)
                self.assertEqual(getattr(link, target_field), target)
                self.assertEqual(link.context_description, "Kontext")
                self.assertEqual(link.sort_order, 7)
                self.assertFalse(link.is_primary)

    def test_update_services_cover_all_six_explicit_targets(self) -> None:
        cases = (
            (
                create_person_attachment,
                update_person_attachment,
                {"person": self.person},
            ),
            (
                create_event_attachment,
                update_event_attachment,
                {"event": self.event},
            ),
            (
                create_relationship_attachment,
                update_relationship_attachment,
                {"relationship": self.relationship},
            ),
            (
                create_residence_attachment,
                update_residence_attachment,
                {"residence": self.residence},
            ),
            (
                create_grave_site_attachment,
                update_grave_site_attachment,
                {"grave_site": self.grave_site},
            ),
            (
                create_place_attachment,
                update_place_attachment,
                {"place": self.place},
            ),
        )

        for create_service, update_service, target in cases:
            with self.subTest(service=update_service.__name__):
                link = create_service(data=self.data(), **target)
                updated = update_service(
                    link=link,
                    data=self.data(context_description="Změněno"),
                    **target,
                )
                self.assertEqual(updated.pk, link.pk)
                self.assertEqual(updated.context_description, "Změněno")

    def test_create_rejects_archived_or_deleted_endpoint_from_fresh_db(self) -> None:
        stale_person = Person.objects.get(pk=self.person.pk)
        self.person.archived_at = timezone.now()
        self.person.save(update_fields=("archived_at",))

        with self.assertRaises(ValidationError) as context:
            create_person_attachment(person=stale_person, data=self.data())
        self.assert_error_code(context.exception, "person", "person_archived")

        self.person.archived_at = None
        self.person.save(update_fields=("archived_at",))
        stale_attachment = Attachment.objects.get(pk=self.attachment.pk)
        self.attachment.deleted_at = timezone.now()
        self.attachment.save(update_fields=("deleted_at",))

        with self.assertRaises(ValidationError) as context:
            create_person_attachment(
                person=self.person,
                data=self.data(attachment=stale_attachment),
            )
        self.assert_error_code(
            context.exception,
            "attachment",
            "attachment_deleted",
        )

        self.attachment.deleted_at = None
        self.attachment.archived_at = timezone.now()
        self.attachment.save(
            update_fields=("deleted_at", "archived_at")
        )
        with self.assertRaises(ValidationError) as context:
            create_person_attachment(
                person=self.person,
                data=self.data(),
            )
        self.assert_error_code(
            context.exception,
            "attachment",
            "attachment_archived",
        )

        self.attachment.archived_at = None
        self.attachment.save(update_fields=("archived_at",))
        self.person.deleted_at = timezone.now()
        self.person.save(update_fields=("deleted_at",))
        with self.assertRaises(ValidationError) as context:
            create_person_attachment(person=self.person, data=self.data())
        self.assert_error_code(context.exception, "person", "person_deleted")

    def test_update_allows_archived_link_and_unchanged_archived_endpoints(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )
        now = timezone.now()
        PersonAttachment.objects.filter(pk=link.pk).update(archived_at=now)
        Person.objects.filter(pk=self.person.pk).update(archived_at=now)
        Attachment.objects.filter(pk=self.attachment.pk).update(
            archived_at=now
        )

        updated = update_person_attachment(
            link=link,
            person=self.person,
            data=self.data(context_description="Zachováno"),
        )

        self.assertEqual(updated.context_description, "Zachováno")
        self.assertEqual(updated.person_id, self.person.pk)
        self.assertEqual(updated.attachment_id, self.attachment.pk)
        self.assertEqual(updated.archived_at, now)

    def test_update_rejects_new_archived_or_deleted_endpoint(
        self,
    ) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )
        self.other_person.archived_at = timezone.now()
        self.other_person.save(update_fields=("archived_at",))

        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.other_person,
                data=self.data(),
            )
        self.assert_error_code(context.exception, "person", "person_archived")

        Person.objects.filter(pk=self.person.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.person,
                data=self.data(),
            )
        self.assert_error_code(context.exception, "person", "person_deleted")

    def test_update_applies_same_lifecycle_rules_to_attachment_endpoint(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )
        replacement = self.make_attachment("charlie")
        replacement.archived_at = timezone.now()
        replacement.save(update_fields=("archived_at",))

        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.person,
                data=self.data(attachment=replacement),
            )
        self.assert_error_code(
            context.exception,
            "attachment",
            "attachment_archived",
        )

        Attachment.objects.filter(pk=self.attachment.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.person,
                data=self.data(),
            )
        self.assert_error_code(
            context.exception,
            "attachment",
            "attachment_deleted",
        )

    def test_update_rejects_soft_deleted_link_from_fresh_db(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )
        PersonAttachment.objects.filter(pk=link.pk).update(
            deleted_at=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.person,
                data=self.data(),
            )
        self.assert_error_code(
            context.exception,
            "link",
            "attachment_link_deleted",
        )

    def test_inactive_role_may_only_be_preserved_on_update(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )
        stale_role = AttachmentRole.objects.get(pk=self.role.pk)
        self.role.is_active = False
        self.role.save(update_fields=("is_active",))

        with self.assertRaises(ValidationError) as context:
            create_person_attachment(
                person=self.other_person,
                data=self.data(role=stale_role),
            )
        self.assert_error_code(context.exception, "role", "role_inactive")

        preserved = update_person_attachment(
            link=link,
            person=self.person,
            data=self.data(role=stale_role, context_description="Zachováno"),
        )
        self.assertEqual(preserved.role_id, self.role.pk)

        other_role = AttachmentRole.objects.create(
            code="inactive_other",
            name="Jiná neaktivní role",
            is_active=False,
        )
        with self.assertRaises(ValidationError) as context:
            update_person_attachment(
                link=link,
                person=self.person,
                data=self.data(role=other_role),
            )
        self.assert_error_code(context.exception, "role", "role_inactive")

    def test_primary_is_generic_person_representation_not_photo_claim(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(is_primary=True),
        )

        self.assertTrue(link.is_primary)
        self.assertEqual(link.attachment.mime_type, "application/pdf")
        self.assertEqual(link.attachment.file_status, "pending")

    def test_person_primary_constraint_uses_soft_delete_not_archive(self) -> None:
        first = create_person_attachment(
            person=self.person,
            data=self.data(is_primary=True),
        )
        second_attachment = self.make_attachment("beta")

        with self.assertRaises(ValidationError) as context:
            create_person_attachment(
                person=self.person,
                data=self.data(
                    attachment=second_attachment,
                    is_primary=True,
                ),
            )
        self.assert_error_code(
            context.exception,
            "__all__",
            "duplicate_primary_person_attachment",
        )

        first.archived_at = timezone.now()
        first.save(update_fields=("archived_at",))
        with self.assertRaises(ValidationError):
            create_person_attachment(
                person=self.person,
                data=self.data(
                    attachment=second_attachment,
                    is_primary=True,
                ),
            )

        first.deleted_at = timezone.now()
        first.save(update_fields=("deleted_at",))
        replacement = create_person_attachment(
            person=self.person,
            data=self.data(
                attachment=second_attachment,
                is_primary=True,
            ),
        )
        self.assertTrue(replacement.is_primary)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                first.deleted_at = None
                first.save(update_fields=("deleted_at",))
        first.refresh_from_db()
        self.assertIsNotNone(first.deleted_at)

    def test_database_itself_enforces_primary_constraint(self) -> None:
        first = PersonAttachment.objects.create(
            person=self.person,
            attachment=self.attachment,
            role=self.role,
            is_primary=True,
        )
        second_attachment = self.make_attachment("delta")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PersonAttachment.objects.create(
                    person=self.person,
                    attachment=second_attachment,
                    role=self.role,
                    is_primary=True,
                )

        first.archived_at = timezone.now()
        first.save(update_fields=("archived_at",))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PersonAttachment.objects.create(
                    person=self.person,
                    attachment=second_attachment,
                    role=self.role,
                    is_primary=True,
                )

        first.deleted_at = timezone.now()
        first.save(update_fields=("deleted_at",))
        PersonAttachment.objects.create(
            person=self.person,
            attachment=second_attachment,
            role=self.role,
            is_primary=True,
        )

    def test_database_primary_conflict_is_mapped_and_rolled_back(self) -> None:
        create_person_attachment(
            person=self.person,
            data=self.data(is_primary=True),
        )
        second_attachment = self.make_attachment("echo")

        with patch.object(PersonAttachment, "full_clean"):
            with self.assertRaises(ValidationError) as context:
                create_person_attachment(
                    person=self.person,
                    data=self.data(
                        attachment=second_attachment,
                        is_primary=True,
                    ),
                )

        self.assert_error_code(
            context.exception,
            "is_primary",
            "duplicate_primary_person_attachment",
        )
        self.assertEqual(
            PersonAttachment.objects.filter(person=self.person).count(),
            1,
        )

    def test_protect_and_link_deletion_preserve_endpoints(self) -> None:
        link = create_person_attachment(
            person=self.person,
            data=self.data(),
        )

        with self.assertRaises(ProtectedError):
            self.person.delete()
        with self.assertRaises(ProtectedError):
            self.attachment.delete()
        with self.assertRaises(ProtectedError):
            self.role.delete()

        link.delete()
        self.assertTrue(Person.objects.filter(pk=self.person.pk).exists())
        self.assertTrue(
            Attachment.objects.filter(pk=self.attachment.pk).exists()
        )
        self.assertTrue(
            AttachmentRole.objects.filter(pk=self.role.pk).exists()
        )

    def test_database_rejects_negative_order(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO materials_personattachment
                        (created_at, updated_at, access_level, archive_reason,
                         deletion_reason, context_description, sort_order,
                         is_primary, attachment_id, person_id, role_id)
                        VALUES (CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                                'public', '', '', '', -1, 0, %s, %s, %s)
                        """,
                        [self.attachment.pk, self.person.pk, self.role.pk],
                    )


class AttachmentLinkMigrationTests(TestCase):
    migration = import_module("materials.migrations.0003_attachment_links")

    def test_migration_has_exact_dependencies_and_models(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("events", "0008_deathdetail"),
                ("materials", "0002_attachments"),
                ("people", "0010_person_titles_biography"),
                ("places", "0009_persongravesite"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(
            tuple(
                operation.name
                for operation in self.migration.Migration.operations
                if isinstance(operation, migrations.CreateModel)
            ),
            (
                "EventAttachment",
                "GraveSiteAttachment",
                "PlaceAttachment",
                "RelationshipAttachment",
                "ResidenceAttachment",
                "PersonAttachment",
            ),
        )

    def test_all_six_tables_exist(self) -> None:
        table_names = connection.introspection.table_names()
        for model in LINK_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIn(model._meta.db_table, table_names)
