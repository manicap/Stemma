from django.db import connection, models
from django.test import SimpleTestCase, TestCase

from .choices import GraveSiteStatus


class GraveSiteStatusTests(SimpleTestCase):
    """Ověření pevného výčtu fyzického stavu hrobového místa."""

    def test_members_values_labels_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(GraveSiteStatus),
            (
                GraveSiteStatus.EXISTING,
                GraveSiteStatus.DESTROYED,
                GraveSiteStatus.UNKNOWN,
            ),
        )
        self.assertEqual(
            GraveSiteStatus.values,
            ["existing", "destroyed", "unknown"],
        )
        self.assertEqual(
            GraveSiteStatus.labels,
            ["Existující", "Zaniklé", "Existence neznámá"],
        )

    def test_values_are_unique_and_only_three_are_defined(self) -> None:
        self.assertEqual(len(GraveSiteStatus), 3)
        self.assertEqual(
            len(set(GraveSiteStatus.values)),
            len(GraveSiteStatus.values),
        )

    def test_is_text_choices_and_not_database_model(self) -> None:
        self.assertTrue(issubclass(GraveSiteStatus, models.TextChoices))
        self.assertFalse(issubclass(GraveSiteStatus, models.Model))
        self.assertFalse(hasattr(GraveSiteStatus, "_meta"))


class GraveSiteStatusDatabaseTests(TestCase):
    """Ověření, že pevný výčet nevytváří vlastní tabulku."""

    def test_does_not_have_database_table(self) -> None:
        self.assertNotIn(
            "places_gravesitestatus",
            connection.introspection.table_names(),
        )
