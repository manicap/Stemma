from importlib import import_module

from django.contrib import admin
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, migrations, models
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.choices import DatePrecision
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
)

from .models import Source, SourceType


class SourceModelTests(TestCase):
    def setUp(self) -> None:
        self.source_type = SourceType.objects.create(
            code="test_archive",
            name="Testovací archivní pramen",
        )

    def source(self, **overrides) -> Source:
        values = {
            "source_type": self.source_type,
            "title": "Matrika narozených",
        }
        values.update(overrides)
        return Source(**values)

    def test_inheritance_fields_and_metadata_are_exact(self) -> None:
        self.assertEqual(
            Source.__bases__,
            (
                TimestampedModel,
                PartialDateModel,
                AccessControlledModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertFalse(hasattr(Source(), "verification_status"))
        self.assertEqual(Source._meta.verbose_name, "Zdroj")
        self.assertEqual(Source._meta.verbose_name_plural, "Zdroje")
        self.assertEqual(Source._meta.ordering, ("title", "pk"))

        source_type = Source._meta.get_field("source_type")
        self.assertIs(source_type.remote_field.model, SourceType)
        self.assertIs(source_type.remote_field.on_delete, models.PROTECT)
        self.assertEqual(source_type.remote_field.related_name, "sources")

    def test_only_type_and_title_are_required_bibliographic_fields(self) -> None:
        source = self.source()

        source.full_clean()
        source.save()

        self.assertEqual(source.full_citation, "")
        self.assertEqual(source.institution, "")
        self.assertEqual(source.fonds, "")
        self.assertEqual(source.shelfmark, "")
        self.assertEqual(source.volume, "")
        self.assertEqual(source.inventory_number, "")
        self.assertEqual(source.creator_name, "")
        self.assertEqual(source.publication_details, "")
        self.assertEqual(source.url, "")
        self.assertIsNone(source.accessed_on)
        self.assertEqual(source.external_identifier, "")
        self.assertEqual(source.note, "")

    def test_title_rejects_missing_or_whitespace_only_value(self) -> None:
        for title, expected_code in (
            ("", "blank"),
            (None, "null"),
            ("   ", "source_title_required"),
        ):
            with self.subTest(title=title):
                with self.assertRaises(ValidationError) as context:
                    self.source(title=title).full_clean()
                self.assertEqual(
                    context.exception.error_dict["title"][0].code,
                    expected_code,
                )

    def test_type_is_required_and_protected(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Source(title="Pramen bez typu").full_clean()
        self.assertEqual(
            context.exception.error_dict["source_type"][0].code,
            "null",
        )

        source = self.source()
        source.save()
        with self.assertRaises(ProtectedError):
            self.source_type.delete()

    def test_optional_bibliography_accepts_partial_values(self) -> None:
        source = self.source(
            institution="Státní oblastní archiv",
            shelfmark="M-12",
            date_precision=DatePrecision.YEAR,
            start_year=1890,
            original_date_text="asi 1890",
            url="https://example.test/source/12",
        )

        source.full_clean()
        source.save()

        self.assertEqual(source.institution, "Státní oblastní archiv")
        self.assertEqual(source.shelfmark, "M-12")
        self.assertEqual(source.start_year, 1890)
        self.assertEqual(source.full_citation, "")

    def test_source_has_no_global_reliability_or_verification_field(self) -> None:
        field_names = {field.name for field in Source._meta.get_fields()}

        self.assertNotIn("reliability", field_names)
        self.assertNotIn("credibility", field_names)
        self.assertNotIn("verification_status", field_names)

    def test_string_representation_uses_trimmed_title_and_safe_fallback(self) -> None:
        self.assertEqual(str(self.source(title="  Matrika  ")), "Matrika")
        self.assertEqual(str(self.source(title="   ")), "Zdroj")
        self.assertEqual(str(self.source(title=None)), "Zdroj")

    def test_table_exists_and_model_is_not_registered_in_admin(self) -> None:
        self.assertIn(
            Source._meta.db_table,
            connection.introspection.table_names(),
        )
        self.assertFalse(admin.site.is_registered(Source))


class SourceMigrationTests(SimpleTestCase):
    migration = import_module("materials.migrations.0005_sources")

    def test_migration_is_single_source_model_after_lookups(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("materials", "0004_source_lookups"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "Source")
