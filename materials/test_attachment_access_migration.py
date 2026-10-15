from importlib import import_module

from django.conf import settings
from django.db import connection, migrations
from django.test import SimpleTestCase, TestCase

from .models import AttachmentAccessGrant, AttachmentAccessRequest


class AttachmentAccessMigrationTests(SimpleTestCase):
    migration = import_module(
        "materials.migrations.0010_attachment_access_requests_and_grants"
    )

    def test_schema_migration_has_expected_dependency_and_operations(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("materials", "0009_vault_attachment_ownership"),
                migrations.swappable_dependency(settings.AUTH_USER_MODEL),
            ],
        )
        operations = self.migration.Migration.operations
        self.assertEqual(
            [
                operation.name
                for operation in operations
                if isinstance(operation, migrations.CreateModel)
            ],
            ["AttachmentAccessRequest", "AttachmentAccessGrant"],
        )
        self.assertEqual(
            [
                operation.constraint.name
                for operation in operations
                if isinstance(operation, migrations.AddConstraint)
            ],
            [
                "materials_unique_pending_access_request",
                "materials_access_request_resolution",
                "materials_unique_active_access_grant",
                "materials_access_grant_revocation",
            ],
        )


class AttachmentAccessMigrationTableTests(TestCase):
    def test_tables_exist(self) -> None:
        tables = connection.introspection.table_names()
        self.assertIn(AttachmentAccessRequest._meta.db_table, tables)
        self.assertIn(AttachmentAccessGrant._meta.db_table, tables)
