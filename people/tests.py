from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.models import LookupModel

from .models import PersonCategory


INITIAL_CATEGORIES = (
    {
        "code": "direct_family",
        "name": "Přímá rodina",
        "description": "Přímí předci a potomci.",
        "sort_order": 10,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "other_family",
        "name": "Ostatní rodina",
        "description": (
            "Vzdálenější příbuzenstvo a osoby příbuzné sňatkem."
        ),
        "sort_order": 20,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "close_to_family",
        "name": "Blízcí rodině",
        "description": (
            "Rodinní přátelé, kmotři a další dlouhodobě blízké osoby."
        ),
        "sort_order": 30,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "clergy",
        "name": "Duchovní",
        "description": (
            "Duchovní významně spojení s rodinou nebo jejím příběhem."
        ),
        "sort_order": 40,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "other_related",
        "name": "Další související osoby",
        "description": "Další osoby důležité pro rodinný příběh.",
        "sort_order": 50,
        "is_active": True,
        "is_system": True,
    },
)
INITIAL_CATEGORY_CODES = tuple(
    category["code"] for category in INITIAL_CATEGORIES
)


class PersonCategoryModelTests(SimpleTestCase):
    """Ověření struktury a metadat číselníku kategorií osob."""

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(PersonCategory._meta.abstract)
        self.assertEqual(PersonCategory.__bases__, (LookupModel,))

    def test_model_has_only_primary_key_and_lookup_fields(self) -> None:
        local_fields = tuple(
            field.name for field in PersonCategory._meta.local_fields
        )

        self.assertEqual(
            local_fields,
            (
                "id",
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
            ),
        )

    def test_model_inherits_expected_field_types(self) -> None:
        expected_types = {
            "id": models.BigAutoField,
            "code": models.CharField,
            "name": models.CharField,
            "description": models.TextField,
            "sort_order": models.PositiveIntegerField,
            "is_active": models.BooleanField,
            "is_system": models.BooleanField,
        }

        for field_name, expected_type in expected_types.items():
            with self.subTest(field_name=field_name):
                self.assertIsInstance(
                    PersonCategory._meta.get_field(field_name),
                    expected_type,
                )

    def test_code_is_unique(self) -> None:
        self.assertTrue(PersonCategory._meta.get_field("code").unique)

    def test_model_metadata(self) -> None:
        self.assertEqual(
            PersonCategory._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(
            PersonCategory._meta.verbose_name,
            "Kategorie osoby",
        )
        self.assertEqual(
            PersonCategory._meta.verbose_name_plural,
            "Kategorie osob",
        )

    def test_string_representation_returns_name(self) -> None:
        category = PersonCategory(code="test", name="Testovací kategorie")

        self.assertEqual(str(category), "Testovací kategorie")


class PersonCategoryDatabaseTests(TestCase):
    """Ověření databázové integrity a výchozích hodnot."""

    def test_duplicate_code_is_rejected(self) -> None:
        PersonCategory.objects.create(code="duplicate", name="První")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PersonCategory.objects.create(
                    code="duplicate",
                    name="Druhá",
                )

    def test_name_does_not_have_to_be_unique(self) -> None:
        PersonCategory.objects.create(code="first", name="Stejný název")
        PersonCategory.objects.create(code="second", name="Stejný název")

        self.assertEqual(
            PersonCategory.objects.filter(name="Stejný název").count(),
            2,
        )

    def test_lookup_defaults(self) -> None:
        category = PersonCategory.objects.create(
            code="defaults",
            name="Výchozí hodnoty",
        )

        self.assertEqual(category.sort_order, 0)
        self.assertTrue(category.is_active)
        self.assertFalse(category.is_system)


class PersonCategoryDataMigrationTests(TestCase):
    """Ověření výchozích dat a vratnosti datové migrace."""

    migration = import_module(
        "people.migrations.0002_initial_person_categories"
    )

    def test_initial_categories_are_present_with_exact_values(self) -> None:
        categories = list(
            PersonCategory.objects.order_by("sort_order").values(
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
            )
        )

        self.assertEqual(categories, list(INITIAL_CATEGORIES))

    def test_forward_migration_is_idempotent(self) -> None:
        PersonCategory.objects.filter(code="direct_family").update(
            name="Dočasně změněný název"
        )

        self.migration.create_initial_person_categories(apps, None)
        self.migration.create_initial_person_categories(apps, None)

        self.assertEqual(PersonCategory.objects.count(), 5)
        self.assertEqual(
            PersonCategory.objects.get(code="direct_family").name,
            "Přímá rodina",
        )

    def test_reverse_migration_removes_only_initial_categories(self) -> None:
        custom_category = PersonCategory.objects.create(
            code="custom",
            name="Vlastní kategorie",
        )

        self.migration.remove_initial_person_categories(apps, None)

        self.assertFalse(
            PersonCategory.objects.filter(
                code__in=INITIAL_CATEGORY_CODES
            ).exists()
        )
        self.assertTrue(
            PersonCategory.objects.filter(pk=custom_category.pk).exists()
        )


class PersonCategoryAdminTests(SimpleTestCase):
    """Ověření registrace číselníku v Django Adminu."""

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(PersonCategory))
