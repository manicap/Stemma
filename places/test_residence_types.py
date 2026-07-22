from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.models import LookupModel

from .admin import ResidenceTypeAdmin
from .models import PlaceType, ResidenceType


EXPECTED_RESIDENCE_TYPES = (
    {
        "code": "primary_residence",
        "name": "Hlavní bydliště",
        "description": (
            "Obvyklé nebo hlavní bydliště osoby v daném období."
        ),
        "sort_order": 10,
    },
    {
        "code": "temporary_residence",
        "name": "Dočasné bydliště",
        "description": (
            "Časově omezené bydliště nebo pobyt mimo hlavní bydliště."
        ),
        "sort_order": 20,
    },
    {
        "code": "official_residence",
        "name": "Úřední bydliště",
        "description": (
            "Administrativně nebo úředně evidovaná adresa, která nemusí "
            "odpovídat skutečnému pobytu."
        ),
        "sort_order": 30,
    },
    {
        "code": "institutional_residence",
        "name": "Institucionální pobyt",
        "description": (
            "Pobyt v instituci, například internátu, kasárnách, nemocnici, "
            "ústavu nebo domově."
        ),
        "sort_order": 40,
    },
    {
        "code": "other",
        "name": "Jiné bydliště",
        "description": (
            "Jiný druh bydliště nebo pobytu nezařaditelný do předchozích "
            "typů."
        ),
        "sort_order": 90,
    },
)
EXPECTED_CODES = tuple(
    residence_type["code"]
    for residence_type in EXPECTED_RESIDENCE_TYPES
)


class ResidenceTypeModelTests(SimpleTestCase):
    """Ověření struktury a metadat číselníku typů bydliště."""

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(ResidenceType._meta.abstract)
        self.assertEqual(ResidenceType.__bases__, (LookupModel,))
        self.assertIs(
            apps.get_model("places", "ResidenceType"),
            ResidenceType,
        )

    def test_model_has_only_primary_key_and_lookup_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in ResidenceType._meta.local_fields),
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

    def test_inherited_field_types_and_options(self) -> None:
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
                    ResidenceType._meta.get_field(field_name),
                    expected_type,
                )

        code = ResidenceType._meta.get_field("code")
        name = ResidenceType._meta.get_field("name")
        description = ResidenceType._meta.get_field("description")
        sort_order = ResidenceType._meta.get_field("sort_order")
        is_active = ResidenceType._meta.get_field("is_active")
        is_system = ResidenceType._meta.get_field("is_system")
        self.assertEqual(code.max_length, 50)
        self.assertTrue(code.unique)
        self.assertEqual(name.max_length, 100)
        self.assertTrue(description.blank)
        self.assertEqual(sort_order.default, 0)
        self.assertIs(is_active.default, True)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_model_metadata_and_string_representation(self) -> None:
        residence_type = ResidenceType(
            code="test",
            name="Testovací bydliště",
        )

        self.assertEqual(
            ResidenceType._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(
            ResidenceType._meta.verbose_name,
            "Typ bydliště",
        )
        self.assertEqual(
            ResidenceType._meta.verbose_name_plural,
            "Typy bydliště",
        )
        self.assertEqual(str(residence_type), "Testovací bydliště")


class ResidenceTypeDatabaseTests(TestCase):
    """Ověření uživatelských typů a databázové integrity."""

    def test_user_type_uses_lookup_defaults(self) -> None:
        residence_type = ResidenceType.objects.create(
            code="seasonal_cottage",
            name="Sezónní pobyt",
        )
        residence_type.refresh_from_db()

        self.assertTrue(residence_type.is_active)
        self.assertFalse(residence_type.is_system)
        self.assertEqual(residence_type.sort_order, 0)

    def test_code_is_unique(self) -> None:
        ResidenceType.objects.create(code="duplicate", name="První")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ResidenceType.objects.create(
                    code="duplicate",
                    name="Druhý",
                )


class ResidenceTypeAdminTests(SimpleTestCase):
    """Ověření lokální konfigurace Django Adminu."""

    def test_model_is_registered_with_approved_configuration(self) -> None:
        self.assertTrue(admin.site.is_registered(ResidenceType))
        model_admin = admin.site._registry[ResidenceType]

        self.assertIsInstance(model_admin, ResidenceTypeAdmin)
        self.assertEqual(
            model_admin.list_display,
            ("code", "name", "sort_order", "is_active", "is_system"),
        )
        self.assertEqual(model_admin.search_fields, ("code", "name"))
        self.assertEqual(
            model_admin.list_filter,
            ("is_active", "is_system"),
        )


class ResidenceTypeSystemDataTests(TestCase):
    """Ověření aplikovaného systémového katalogu."""

    def test_exact_system_catalog_is_present(self) -> None:
        system_types = ResidenceType.objects.filter(is_system=True)

        self.assertEqual(system_types.count(), 5)
        self.assertEqual(
            list(
                system_types.values(
                    "code",
                    "name",
                    "description",
                    "sort_order",
                )
            ),
            list(EXPECTED_RESIDENCE_TYPES),
        )
        self.assertFalse(system_types.filter(is_active=False).exists())

    def test_default_ordering_matches_approved_catalog(self) -> None:
        self.assertEqual(
            list(
                ResidenceType.objects.filter(is_system=True).values_list(
                    "code",
                    flat=True,
                )
            ),
            list(EXPECTED_CODES),
        )

    def test_user_type_can_coexist_with_system_catalog(self) -> None:
        ResidenceType.objects.create(
            code="user_defined",
            name="Uživatelský typ",
        )

        self.assertEqual(
            ResidenceType.objects.filter(is_system=True).count(),
            5,
        )
        self.assertTrue(
            ResidenceType.objects.filter(
                code="user_defined",
                is_system=False,
            ).exists()
        )


class ResidenceTypeMigrationHelperTests(TestCase):
    """Ověření idempotence, kolizí a reverse datové migrace."""

    migration = import_module(
        "places.migrations.0004_initial_residence_types"
    )

    def test_forward_is_idempotent_and_repairs_system_values(self) -> None:
        ResidenceType.objects.filter(code="primary_residence").update(
            name="Změněný název",
            description="Změněný popis",
            sort_order=999,
            is_active=False,
        )

        self.migration.create_initial_residence_types(apps, None)
        self.migration.create_initial_residence_types(apps, None)

        self.assertEqual(
            ResidenceType.objects.filter(
                code__in=EXPECTED_CODES,
                is_system=True,
            ).count(),
            5,
        )
        primary = ResidenceType.objects.get(code="primary_residence")
        self.assertEqual(primary.name, "Hlavní bydliště")
        self.assertEqual(
            primary.description,
            "Obvyklé nebo hlavní bydliště osoby v daném období.",
        )
        self.assertEqual(primary.sort_order, 10)
        self.assertTrue(primary.is_active)

    def test_collision_fails_before_any_catalog_write(self) -> None:
        ResidenceType.objects.all().delete()
        conflict = ResidenceType.objects.create(
            code="primary_residence",
            name="Uživatelský konflikt",
            description="Nesmí se změnit.",
            sort_order=777,
        )
        existing_system = ResidenceType.objects.create(
            code="temporary_residence",
            name="Původní systémový název",
            description="Původní systémový popis.",
            sort_order=888,
            is_active=False,
            is_system=True,
        )

        with self.assertRaisesRegex(RuntimeError, "primary_residence"):
            self.migration.create_initial_residence_types(apps, None)

        conflict.refresh_from_db()
        existing_system.refresh_from_db()
        self.assertEqual(conflict.name, "Uživatelský konflikt")
        self.assertEqual(conflict.description, "Nesmí se změnit.")
        self.assertEqual(conflict.sort_order, 777)
        self.assertFalse(conflict.is_system)
        self.assertEqual(
            existing_system.name,
            "Původní systémový název",
        )
        self.assertFalse(existing_system.is_active)
        self.assertEqual(
            set(ResidenceType.objects.values_list("code", flat=True)),
            {"primary_residence", "temporary_residence"},
        )

    def test_reverse_removes_only_current_system_catalog_rows(self) -> None:
        ResidenceType.objects.filter(code="other").update(is_system=False)
        user_type = ResidenceType.objects.create(
            code="user_reverse",
            name="Uživatelský typ",
        )
        place_type = PlaceType.objects.create(
            code="reverse_place_type",
            name="Typ místa",
        )

        self.migration.remove_initial_residence_types(apps, None)

        self.assertEqual(
            set(ResidenceType.objects.values_list("code", flat=True)),
            {"other", user_type.code},
        )
        self.assertFalse(
            ResidenceType.objects.get(code="other").is_system
        )
        self.assertTrue(
            PlaceType.objects.filter(pk=place_type.pk).exists()
        )
