from importlib import import_module

from django.contrib import admin
from django.apps import apps
from django.conf import settings
from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase

from common.admin import SystemValueAdminMixin
from common.models import LookupModel

from .models import Attachment, AttachmentCategory, AttachmentRole


class MaterialsApplicationTests(SimpleTestCase):
    def test_application_is_registered(self) -> None:
        config = apps.get_app_config("materials")

        self.assertEqual(config.name, "materials")
        self.assertEqual(config.verbose_name, "Materiály a zdroje")
        self.assertIn(
            "materials.apps.MaterialsConfig",
            settings.INSTALLED_APPS,
        )
        self.assertEqual(
            tuple(config.get_models()),
            (AttachmentCategory, AttachmentRole, Attachment),
        )


class AttachmentLookupModelTests(TestCase):
    models = (AttachmentCategory, AttachmentRole)

    def test_models_are_plain_lookup_models_with_exact_metadata(self) -> None:
        expected_labels = {
            AttachmentCategory: ("Kategorie přílohy", "Kategorie příloh"),
            AttachmentRole: ("Role přílohy", "Role příloh"),
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
        self.assertFalse(AttachmentCategory.objects.exists())
        self.assertFalse(AttachmentRole.objects.exists())

    def test_string_representation_uses_name(self) -> None:
        category = AttachmentCategory(code="photo", name="Fotografie")
        role = AttachmentRole(code="illustration", name="Ilustrace")

        self.assertEqual(str(category), "Fotografie")
        self.assertEqual(str(role), "Ilustrace")

    def test_database_tables_exist(self) -> None:
        table_names = connection.introspection.table_names()

        self.assertIn(AttachmentCategory._meta.db_table, table_names)
        self.assertIn(AttachmentRole._meta.db_table, table_names)


class AttachmentLookupAdminTests(SimpleTestCase):
    def test_admin_uses_system_value_guard(self) -> None:
        for model in (AttachmentCategory, AttachmentRole):
            with self.subTest(model=model.__name__):
                self.assertIsInstance(
                    admin.site._registry[model],
                    SystemValueAdminMixin,
                )


class AttachmentLookupMigrationTests(SimpleTestCase):
    migration = import_module(
        "materials.migrations.0001_attachment_lookups"
    )

    def test_migration_has_no_dependencies_and_exact_models(self) -> None:
        self.assertEqual(self.migration.Migration.dependencies, [])
        self.assertEqual(len(self.migration.Migration.operations), 2)
        self.assertEqual(
            tuple(
                operation.name
                for operation in self.migration.Migration.operations
                if isinstance(operation, migrations.CreateModel)
            ),
            ("AttachmentCategory", "AttachmentRole"),
        )
