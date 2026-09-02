from importlib import import_module

from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, migrations, models
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    TimestampedModel,
)
from events.models import Event
from people.models import PersonName, Relationship
from places.models import GraveSite, Residence

from .choices import SourceSupport
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentSource,
    EventSource,
    GraveSiteSource,
    PersonNameSource,
    RelationshipSource,
    ResidenceSource,
    Source,
    SourceLinkModel,
    SourceRole,
    SourceType,
)


LINK_MODELS = (
    PersonNameSource,
    EventSource,
    RelationshipSource,
    ResidenceSource,
    GraveSiteSource,
    AttachmentSource,
)


class SourceSupportTests(SimpleTestCase):
    def test_values_labels_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(SourceSupport),
            (
                SourceSupport.CONFIRMS,
                SourceSupport.SUGGESTS,
                SourceSupport.SUPPLEMENTS,
                SourceSupport.CONTRADICTS,
            ),
        )
        self.assertEqual(
            SourceSupport.values,
            ["confirms", "suggests", "supplements", "contradicts"],
        )


class SourceLinkStructureTests(TestCase):
    def test_abstract_base_has_exact_policy_and_business_fields(self) -> None:
        self.assertTrue(SourceLinkModel._meta.abstract)
        self.assertEqual(
            SourceLinkModel.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertEqual(
            {field.name for field in SourceLinkModel._meta.local_fields},
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
                "source",
                "role",
                "cited_part",
                "excerpt",
                "interpretation",
                "support_strength",
            },
        )
        self.assertEqual(
            SourceLinkModel._meta.get_field("support_strength").choices,
            SourceSupport.choices,
        )
        self.assertEqual(
            SourceLinkModel._meta.get_field("support_strength").default,
            models.NOT_PROVIDED,
        )

    def test_six_models_have_exact_explicit_targets_and_protection(self) -> None:
        specifications = (
            (
                PersonNameSource,
                "person_name",
                PersonName,
                "personnamesource_links",
            ),
            (EventSource, "event", Event, "eventsource_links"),
            (
                RelationshipSource,
                "relationship",
                Relationship,
                "relationshipsource_links",
            ),
            (ResidenceSource, "residence", Residence, "residencesource_links"),
            (
                GraveSiteSource,
                "grave_site",
                GraveSite,
                "gravesitesource_links",
            ),
            (
                AttachmentSource,
                "attachment",
                Attachment,
                "attachmentsource_links",
            ),
        )

        for model, target_name, target_model, source_reverse in specifications:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.__bases__, (SourceLinkModel,))
                target = model._meta.get_field(target_name)
                source = model._meta.get_field("source")
                role = model._meta.get_field("role")
                self.assertIs(target.remote_field.model, target_model)
                self.assertIs(target.remote_field.on_delete, models.PROTECT)
                self.assertEqual(
                    target.remote_field.related_name,
                    "source_links",
                )
                self.assertIs(source.remote_field.model, Source)
                self.assertIs(source.remote_field.on_delete, models.PROTECT)
                self.assertEqual(source.remote_field.related_name, source_reverse)
                self.assertIs(role.remote_field.model, SourceRole)
                self.assertIs(role.remote_field.on_delete, models.PROTECT)
                self.assertFalse(admin.site.is_registered(model))

    def test_tables_exist_and_no_generic_relation_is_present(self) -> None:
        table_names = connection.introspection.table_names()
        for model in LINK_MODELS:
            with self.subTest(model=model.__name__):
                self.assertIn(model._meta.db_table, table_names)
                field_names = {field.name for field in model._meta.get_fields()}
                self.assertNotIn("content_type", field_names)
                self.assertNotIn("object_id", field_names)


class SourceLinkDatabaseTests(TestCase):
    def setUp(self) -> None:
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archivní pramen",
        )
        self.role = SourceRole.objects.create(
            code="evidence",
            name="Doklad",
        )
        self.source = Source.objects.create(
            source_type=self.source_type,
            title="Matrika",
        )
        category = AttachmentCategory.objects.create(
            code="scan",
            name="Sken",
        )
        self.attachment = Attachment.objects.create(
            category=category,
            original_filename="scan.pdf",
            storage_key="attachments/source-link.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="a" * 64,
        )

    def link(self, **overrides) -> AttachmentSource:
        values = {
            "attachment": self.attachment,
            "source": self.source,
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
        }
        values.update(overrides)
        return AttachmentSource(**values)

    def test_required_support_and_optional_context_are_validated(self) -> None:
        link = self.link()
        link.full_clean()
        link.save()

        self.assertEqual(link.cited_part, "")
        self.assertEqual(link.excerpt, "")
        self.assertEqual(link.interpretation, "")

        for value, expected_code in (
            ("", "blank"),
            ("unknown", "invalid_choice"),
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError) as context:
                    self.link(support_strength=value).full_clean()
                self.assertEqual(
                    context.exception.error_dict["support_strength"][0].code,
                    expected_code,
                )

    def test_source_role_and_target_are_protected(self) -> None:
        self.link().save()

        for protected in (self.source, self.role, self.attachment):
            with self.subTest(model=type(protected).__name__):
                with self.assertRaises(ProtectedError):
                    protected.delete()


class SourceLinkMigrationTests(SimpleTestCase):
    migration = import_module("materials.migrations.0006_source_links")

    def test_migration_has_exact_dependency_and_models(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("events", "0008_deathdetail"),
                ("materials", "0005_sources"),
                ("people", "0010_person_titles_biography"),
                ("places", "0009_persongravesite"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 6)
        self.assertEqual(
            tuple(
                operation.name
                for operation in self.migration.Migration.operations
                if isinstance(operation, migrations.CreateModel)
            ),
            (
                "AttachmentSource",
                "EventSource",
                "GraveSiteSource",
                "PersonNameSource",
                "RelationshipSource",
                "ResidenceSource",
            ),
        )
