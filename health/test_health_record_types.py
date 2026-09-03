from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.db import IntegrityError, connection, migrations, transaction
from django.test import SimpleTestCase, TestCase

from common.admin import SystemValueAdminMixin
from common.models import LookupModel

from .models import HealthRecord, HealthRecordType


class HealthRecordTypeModelTests(TestCase):
    def test_app_is_registered_with_expected_configuration(self) -> None:
        app_config = apps.get_app_config("health")

        self.assertEqual(app_config.name, "health")
        self.assertEqual(app_config.verbose_name, "Zdravotní informace")

    def test_model_is_plain_lookup_with_exact_metadata(self) -> None:
        self.assertEqual(HealthRecordType.__bases__, (LookupModel,))
        self.assertEqual(
            {field.name for field in HealthRecordType._meta.local_fields},
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
        self.assertEqual(
            HealthRecordType._meta.verbose_name,
            "Typ zdravotního záznamu",
        )
        self.assertEqual(
            HealthRecordType._meta.verbose_name_plural,
            "Typy zdravotních záznamů",
        )
        self.assertEqual(
            HealthRecordType._meta.ordering,
            ("sort_order", "name", "code"),
        )

    def test_catalog_starts_empty_without_invented_system_values(self) -> None:
        self.assertFalse(HealthRecordType.objects.exists())

    def test_user_value_uses_lookup_defaults_and_unique_code(self) -> None:
        record_type = HealthRecordType.objects.create(
            code="custom",
            name="Vlastní zdravotní typ",
        )

        self.assertTrue(record_type.is_active)
        self.assertFalse(record_type.is_system)
        self.assertEqual(record_type.sort_order, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            HealthRecordType.objects.create(
                code="custom",
                name="Duplicitní kód",
            )

    def test_string_representation_uses_name(self) -> None:
        record_type = HealthRecordType(
            code="custom",
            name="Vlastní zdravotní typ",
        )

        self.assertEqual(str(record_type), "Vlastní zdravotní typ")

    def test_database_table_exists(self) -> None:
        self.assertIn(
            HealthRecordType._meta.db_table,
            connection.introspection.table_names(),
        )

    def test_app_contains_only_approved_models(self) -> None:
        self.assertEqual(
            {model.__name__ for model in apps.get_app_config("health").get_models()},
            {"HealthRecord", "HealthRecordType"},
        )


class HealthRecordTypeAdminTests(SimpleTestCase):
    def test_admin_uses_system_value_guard(self) -> None:
        self.assertIsInstance(
            admin.site._registry[HealthRecordType],
            SystemValueAdminMixin,
        )

    def test_sensitive_record_is_not_registered_in_admin(self) -> None:
        self.assertNotIn(HealthRecord, admin.site._registry)


class HealthRecordTypeMigrationTests(SimpleTestCase):
    migration = import_module("health.migrations.0001_health_record_types")

    def test_migration_is_structural_and_creates_only_lookup(self) -> None:
        self.assertEqual(self.migration.Migration.dependencies, [])
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "HealthRecordType")
