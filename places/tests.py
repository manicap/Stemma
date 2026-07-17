from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.models import LookupModel

from .apps import PlacesConfig
from .models import PlaceType


class PlacesApplicationTests(SimpleTestCase):
    """Ověření konfigurace a registrace aplikace places."""

    def test_app_config_exists_and_is_registered(self) -> None:
        app_config = apps.get_app_config("places")

        self.assertIsInstance(app_config, PlacesConfig)
        self.assertEqual(app_config.name, "places")
        self.assertEqual(app_config.label, "places")
        self.assertIn("places.apps.PlacesConfig", settings.INSTALLED_APPS)
        self.assertIs(apps.get_model("places", "PlaceType"), PlaceType)


class PlaceTypeModelTests(SimpleTestCase):
    """Ověření struktury a metadat číselníku typů míst."""

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(PlaceType._meta.abstract)
        self.assertEqual(PlaceType.__bases__, (LookupModel,))

    def test_model_has_only_primary_key_and_lookup_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in PlaceType._meta.local_fields),
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
                    PlaceType._meta.get_field(field_name),
                    expected_type,
                )

    def test_inherited_field_options(self) -> None:
        code = PlaceType._meta.get_field("code")
        description = PlaceType._meta.get_field("description")
        sort_order = PlaceType._meta.get_field("sort_order")
        is_active = PlaceType._meta.get_field("is_active")
        is_system = PlaceType._meta.get_field("is_system")

        self.assertTrue(code.unique)
        self.assertTrue(description.blank)
        self.assertEqual(sort_order.default, 0)
        self.assertIs(is_active.default, True)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_model_metadata(self) -> None:
        self.assertEqual(
            PlaceType._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(PlaceType._meta.verbose_name, "Typ místa")
        self.assertEqual(
            PlaceType._meta.verbose_name_plural,
            "Typy míst",
        )

    def test_string_representation_returns_name(self) -> None:
        place_type = PlaceType(code="test", name="Testovací typ")

        self.assertEqual(str(place_type), "Testovací typ")


class PlaceTypeDatabaseTests(TestCase):
    """Ověření databázové integrity a řazení typů míst."""

    def test_duplicate_code_is_rejected(self) -> None:
        PlaceType.objects.create(code="duplicate", name="První")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PlaceType.objects.create(code="duplicate", name="Druhý")

    def test_name_does_not_have_to_be_unique(self) -> None:
        PlaceType.objects.create(code="first", name="Stejný název")
        PlaceType.objects.create(code="second", name="Stejný název")

        self.assertEqual(
            PlaceType.objects.filter(name="Stejný název").count(),
            2,
        )

    def test_lookup_defaults_are_persisted(self) -> None:
        place_type = PlaceType.objects.create(
            code="defaults",
            name="Výchozí hodnoty",
        )
        place_type.refresh_from_db()

        self.assertEqual(place_type.sort_order, 0)
        self.assertTrue(place_type.is_active)
        self.assertFalse(place_type.is_system)

    def test_default_queryset_ordering(self) -> None:
        PlaceType.objects.create(code="z", name="Beta", sort_order=20)
        PlaceType.objects.create(code="b", name="Alfa", sort_order=10)
        PlaceType.objects.create(code="a", name="Alfa", sort_order=10)

        self.assertEqual(
            list(PlaceType.objects.values_list("code", flat=True)),
            ["a", "b", "z"],
        )


class PlaceTypeAdminTests(SimpleTestCase):
    """Ověření registrace typu místa v Django Adminu."""

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(PlaceType))
