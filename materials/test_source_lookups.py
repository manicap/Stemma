from importlib import import_module

from django.contrib import admin
from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase

from common.admin import SystemValueAdminMixin
from common.models import LookupModel

from .models import SourceRole, SourceType


class SourceLookupModelTests(TestCase):
    models = (SourceType, SourceRole)

    def test_models_are_plain_lookup_models_with_exact_metadata(self) -> None:
        expected_labels = {
            SourceType: ("Typ zdroje", "Typy zdrojů"),
            SourceRole: ("Role zdroje", "Role zdrojů"),
        }

        for model in self.models:
            with self.subTest(model=model.__name__):
                self.assertEqual(model.__bases__, (LookupModel,))
                self.assertEqual(
                    {field.name for field in model._meta.local_fields},
                    {
                        "id",
                        "code",
                        "name",
                        "description",
                        "sort_order",
                        "is_active",
                        "is_system",
                    },
                )
                singular, plural = expected_labels[model]
                self.assertEqual(model._meta.verbose_name, singular)
                self.assertEqual(model._meta.verbose_name_plural, plural)
                self.assertEqual(
                    model._meta.ordering,
                    ("sort_order", "name", "code"),
                )

    def test_catalogs_start_empty_without_invented_system_values(self) -> None:
        self.assertFalse(SourceType.objects.exists())
        self.assertFalse(SourceRole.objects.exists())

    def test_string_representation_uses_name(self) -> None:
        source_type = SourceType(code="archive", name="Archivní pramen")
        source_role = SourceRole(code="supports", name="Dokládá")

        self.assertEqual(str(source_type), "Archivní pramen")
        self.assertEqual(str(source_role), "Dokládá")

    def test_database_tables_exist(self) -> None:
        table_names = connection.introspection.table_names()

        self.assertIn(SourceType._meta.db_table, table_names)
        self.assertIn(SourceRole._meta.db_table, table_names)


class SourceLookupAdminTests(SimpleTestCase):
    def test_admin_uses_system_value_guard(self) -> None:
        for model in (SourceType, SourceRole):
            with self.subTest(model=model.__name__):
                self.assertIsInstance(
                    admin.site._registry[model],
                    SystemValueAdminMixin,
                )


class SourceLookupMigrationTests(SimpleTestCase):
    migration = import_module("materials.migrations.0004_source_lookups")

    def test_migration_has_exact_dependency_and_models(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [("materials", "0003_attachment_links")],
        )
        self.assertEqual(len(self.migration.Migration.operations), 2)
        self.assertEqual(
            tuple(
                operation.name
                for operation in self.migration.Migration.operations
                if isinstance(operation, migrations.CreateModel)
            ),
            ("SourceType", "SourceRole"),
        )
