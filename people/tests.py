from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.choices import AccessLevel, Gender, VerificationStatus
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    TimestampedModel,
    VerifiableModel,
)

from .models import Person, PersonCategory


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


class PersonModelTests(SimpleTestCase):
    """Ověření struktury, metadat a validace osoby."""

    inherited_field_names = {
        "id",
        "created_at",
        "updated_at",
        "created_by",
        "access_level",
        "verification_status",
        "archived_at",
        "archived_by",
        "archive_reason",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
    }

    def test_model_is_concrete_and_uses_common_models(self) -> None:
        self.assertFalse(Person._meta.abstract)
        self.assertEqual(
            Person.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                VerifiableModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )

    def test_model_has_only_expected_identity_fields(self) -> None:
        identity_fields = tuple(
            field.name
            for field in Person._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            identity_fields,
            ("category", "gender", "first_name", "last_name", "notes"),
        )

    def test_inherited_fields_are_present(self) -> None:
        field_names = {
            field.name for field in Person._meta.local_fields
        }

        self.assertTrue(self.inherited_field_names <= field_names)

    def test_identity_field_types_and_options(self) -> None:
        category = Person._meta.get_field("category")
        gender = Person._meta.get_field("gender")
        first_name = Person._meta.get_field("first_name")
        last_name = Person._meta.get_field("last_name")
        notes = Person._meta.get_field("notes")

        self.assertIsInstance(category, models.ForeignKey)
        self.assertIsInstance(gender, models.CharField)
        self.assertEqual(gender.max_length, 10)
        self.assertEqual(gender.choices, Gender.choices)
        self.assertEqual(gender.default, Gender.UNKNOWN)
        self.assertIsInstance(first_name, models.CharField)
        self.assertEqual(first_name.max_length, 100)
        self.assertTrue(first_name.blank)
        self.assertIsInstance(last_name, models.CharField)
        self.assertEqual(last_name.max_length, 100)
        self.assertTrue(last_name.blank)
        self.assertIsInstance(notes, models.TextField)
        self.assertTrue(notes.blank)

    def test_category_relation(self) -> None:
        field = Person._meta.get_field("category")

        self.assertIs(field.remote_field.model, PersonCategory)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertEqual(field.remote_field.related_name, "persons")

    def test_inherited_and_lifecycle_defaults(self) -> None:
        person = Person()

        self.assertEqual(person.gender, Gender.UNKNOWN)
        self.assertEqual(person.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            person.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertIsNone(person.created_by)
        self.assertIsNone(person.archived_at)
        self.assertIsNone(person.archived_by)
        self.assertEqual(person.archive_reason, "")
        self.assertIsNone(person.deleted_at)
        self.assertIsNone(person.deleted_by)
        self.assertEqual(person.deletion_reason, "")

    def test_model_metadata(self) -> None:
        self.assertEqual(
            Person._meta.ordering,
            ("last_name", "first_name"),
        )
        self.assertEqual(Person._meta.verbose_name, "Osoba")
        self.assertEqual(Person._meta.verbose_name_plural, "Osoby")

    def test_string_representation(self) -> None:
        cases = (
            (Person(first_name="Jan", last_name="Novák"), "Novák Jan"),
            (Person(first_name="Jan"), "Jan"),
            (Person(last_name="Novák"), "Novák"),
            (Person(), ""),
        )

        for person, expected in cases:
            with self.subTest(
                first_name=person.first_name,
                last_name=person.last_name,
            ):
                self.assertEqual(str(person), expected)

    def test_at_least_one_main_name_is_required(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            "alespoň jméno nebo příjmení",
        ):
            Person().full_clean()

    def test_either_main_name_is_valid(self) -> None:
        for person in (
            Person(first_name="Jan"),
            Person(last_name="Novák"),
        ):
            with self.subTest(
                first_name=person.first_name,
                last_name=person.last_name,
            ):
                person.full_clean()


class PersonDatabaseTests(TestCase):
    """Ověření databázových pravidel osoby."""

    def test_people_can_have_identical_names(self) -> None:
        Person.objects.create(first_name="Jan", last_name="Novák")
        Person.objects.create(first_name="Jan", last_name="Novák")

        self.assertEqual(
            Person.objects.filter(
                first_name="Jan",
                last_name="Novák",
            ).count(),
            2,
        )

    def test_main_names_are_not_unique(self) -> None:
        self.assertFalse(Person._meta.get_field("first_name").unique)
        self.assertFalse(Person._meta.get_field("last_name").unique)

    def test_person_category_is_protected(self) -> None:
        category = PersonCategory.objects.create(
            code="protected",
            name="Chráněná kategorie",
        )
        Person.objects.create(
            category=category,
            first_name="Jan",
            last_name="Novák",
        )

        with self.assertRaises(ProtectedError):
            category.delete()


class PersonAdminTests(SimpleTestCase):
    """Ověření registrace osoby v Django Adminu."""

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(Person))
