from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class VaultOwnershipMigrationTests(TransactionTestCase):
    migrate_from = ("materials", "0008_health_record_source")
    migrate_to = ("materials", "0009_vault_attachment_ownership")

    def setUp(self) -> None:
        super().setUp()
        self._schema_restored = False
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.addCleanup(self._restore_latest_schema)
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        user_model = old_apps.get_model("accounts", "User")
        self.owner_ids = (
            user_model.objects.create(username="existing-first").pk,
            user_model.objects.create(username="existing-second").pk,
        )

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.migrated_apps = executor.loader.project_state(
            [self.migrate_to]
        ).apps

    def tearDown(self) -> None:
        self._restore_latest_schema()
        super().tearDown()

    def _restore_latest_schema(self) -> None:
        if self._schema_restored:
            return
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        self._schema_restored = True

    def test_existing_users_receive_one_owned_vault_each(self) -> None:
        vault = self.migrated_apps.get_model("materials", "Vault")
        attachment = self.migrated_apps.get_model("materials", "Attachment")

        self.assertEqual(
            set(vault.objects.values_list("owner_id", flat=True)),
            set(self.owner_ids),
        )
        self.assertFalse(attachment._meta.get_field("vault").null)
        self.assertEqual(
            attachment._meta.get_field("privacy_status").default,
            "standard",
        )


class VaultOwnershipLegacyAttachmentMigrationTests(TransactionTestCase):
    migrate_from = ("materials", "0008_health_record_source")
    migrate_to = ("materials", "0009_vault_attachment_ownership")

    def setUp(self) -> None:
        super().setUp()
        self._schema_restored = False
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.addCleanup(self._restore_latest_schema)
        self.old_apps = executor.loader.project_state([self.migrate_from]).apps
        category = self.old_apps.get_model(
            "materials",
            "AttachmentCategory",
        ).objects.create(code="legacy", name="Legacy")
        self.legacy_attachment = self.old_apps.get_model(
            "materials",
            "Attachment",
        ).objects.create(
            category=category,
            original_filename="legacy.pdf",
            storage_key="legacy/legacy.pdf",
            mime_type="application/pdf",
            size_bytes=1,
            sha256="f" * 64,
        )

    def tearDown(self) -> None:
        self._restore_latest_schema()
        super().tearDown()

    def _restore_latest_schema(self) -> None:
        if self._schema_restored:
            return
        attachment = self.old_apps.get_model("materials", "Attachment")
        attachment.objects.filter(pk=self.legacy_attachment.pk).delete()
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        self._schema_restored = True

    def test_legacy_attachment_aborts_migration_before_required_vault(self) -> None:
        executor = MigrationExecutor(connection)

        with self.assertRaisesMessage(
            RuntimeError,
            "M3.1 vyžaduje čistou vývojovou databázi bez legacy příloh",
        ):
            executor.migrate([self.migrate_to])
