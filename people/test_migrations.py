from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PersonTitlesBiographyMigrationTests(TransactionTestCase):
    migrate_from = ("people", "0009_alter_person_options")
    migrate_to = ("people", "0010_person_titles_biography")

    def setUp(self) -> None:
        super().setUp()
        self._schema_restored = False
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        self.addCleanup(self._restore_latest_schema)
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        old_person = old_apps.get_model("people", "Person")
        self.person_pk = old_person.objects.create(
            first_name="Anna",
            notes="Existující poznámka.",
        ).pk

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

    def test_existing_person_is_preserved_with_empty_new_fields(self) -> None:
        person_model = self.migrated_apps.get_model("people", "Person")

        person = person_model.objects.get(pk=self.person_pk)

        self.assertEqual(person.first_name, "Anna")
        self.assertEqual(person.notes, "Existující poznámka.")
        self.assertEqual(person.title_before_name, "")
        self.assertEqual(person.title_after_name, "")
        self.assertEqual(person.biography, "")
