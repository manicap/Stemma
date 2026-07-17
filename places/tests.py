from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    TimestampedModel,
    VerifiableModel,
)

from .apps import PlacesConfig
from .models import Place, PlaceType


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


class PlaceModelTests(SimpleTestCase):
    """Ověření struktury, metadat a validace místa."""

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

    @staticmethod
    def make_place(**overrides) -> Place:
        values = {
            "name": "Praha",
            "normalized_name": "praha",
        }
        values.update(overrides)
        return Place(**values)

    def assert_validation_code(
        self,
        place: Place,
        field_name: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            place.full_clean()

        self.assertIn(field_name, context.exception.error_dict)
        self.assertIn(
            code,
            {
                error.code
                for error in context.exception.error_dict[field_name]
            },
        )

    def test_model_is_concrete_and_uses_common_models(self) -> None:
        self.assertFalse(Place._meta.abstract)
        self.assertEqual(
            Place.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                VerifiableModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertIs(apps.get_model("places", "Place"), Place)

    def test_model_has_only_expected_place_fields(self) -> None:
        place_fields = tuple(
            field.name
            for field in Place._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            place_fields,
            (
                "place_type",
                "name",
                "normalized_name",
                "parent",
                "country",
                "description",
                "latitude",
                "longitude",
                "coordinate_precision_m",
            ),
        )

    def test_inherited_fields_are_present(self) -> None:
        field_names = {
            field.name for field in Place._meta.local_fields
        }

        self.assertTrue(self.inherited_field_names <= field_names)

    def test_place_type_relation(self) -> None:
        field = Place._meta.get_field("place_type")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, PlaceType)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(field.remote_field.related_name, "places")

    def test_name_fields(self) -> None:
        name = Place._meta.get_field("name")
        normalized_name = Place._meta.get_field("normalized_name")

        self.assertIsInstance(name, models.CharField)
        self.assertEqual(name.max_length, 255)
        self.assertFalse(name.blank)
        self.assertFalse(name.unique)
        self.assertIsInstance(normalized_name, models.CharField)
        self.assertEqual(normalized_name.max_length, 255)
        self.assertFalse(normalized_name.blank)
        self.assertFalse(normalized_name.unique)
        self.assertTrue(normalized_name.db_index)

    def test_name_and_normalized_name_are_required(self) -> None:
        place = Place()

        with self.assertRaises(ValidationError) as context:
            place.full_clean()

        self.assertEqual(
            {"name", "normalized_name"},
            {"name", "normalized_name"}
            & set(context.exception.error_dict),
        )

    def test_normalized_name_is_not_generated_or_changed(self) -> None:
        place = self.make_place(
            name="Český Krumlov",
            normalized_name="rucne zadana hodnota",
        )

        place.full_clean()

        self.assertEqual(place.normalized_name, "rucne zadana hodnota")

    def test_parent_relation(self) -> None:
        field = Place._meta.get_field("parent")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, Place)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertIs(field.remote_field.on_delete, models.SET_NULL)
        self.assertEqual(field.remote_field.related_name, "children")

    def test_country_and_description_fields(self) -> None:
        country = Place._meta.get_field("country")
        description = Place._meta.get_field("description")

        self.assertIsInstance(country, models.CharField)
        self.assertEqual(country.max_length, 100)
        self.assertTrue(country.blank)
        self.assertFalse(country.null)
        self.assertIsInstance(description, models.TextField)
        self.assertTrue(description.blank)
        self.assertFalse(description.null)

    def test_coordinate_field_types_and_options(self) -> None:
        latitude = Place._meta.get_field("latitude")
        longitude = Place._meta.get_field("longitude")
        precision = Place._meta.get_field("coordinate_precision_m")

        self.assertIsInstance(latitude, models.DecimalField)
        self.assertEqual(latitude.max_digits, 8)
        self.assertEqual(latitude.decimal_places, 6)
        self.assertTrue(latitude.null)
        self.assertTrue(latitude.blank)
        self.assertIsInstance(longitude, models.DecimalField)
        self.assertEqual(longitude.max_digits, 9)
        self.assertEqual(longitude.decimal_places, 6)
        self.assertTrue(longitude.null)
        self.assertTrue(longitude.blank)
        self.assertIsInstance(precision, models.PositiveIntegerField)
        self.assertTrue(precision.null)
        self.assertTrue(precision.blank)

    def test_both_coordinates_may_be_blank(self) -> None:
        self.make_place().full_clean()

    def test_coordinate_boundaries_and_zero_are_valid(self) -> None:
        cases = (
            (Decimal("-90"), Decimal("-180")),
            (Decimal("90"), Decimal("180")),
            (Decimal("0"), Decimal("0")),
        )

        for latitude, longitude in cases:
            with self.subTest(latitude=latitude, longitude=longitude):
                self.make_place(
                    latitude=latitude,
                    longitude=longitude,
                ).full_clean()

    def test_latitude_out_of_range_has_stable_code(self) -> None:
        self.assert_validation_code(
            self.make_place(
                latitude=Decimal("90.000001"),
                longitude=Decimal("0"),
            ),
            "latitude",
            "latitude_out_of_range",
        )

    def test_longitude_out_of_range_has_stable_code(self) -> None:
        self.assert_validation_code(
            self.make_place(
                latitude=Decimal("0"),
                longitude=Decimal("180.000001"),
            ),
            "longitude",
            "longitude_out_of_range",
        )

    def test_single_coordinate_has_stable_code(self) -> None:
        cases = (
            ({"latitude": Decimal("50")}, "longitude"),
            ({"longitude": Decimal("14")}, "latitude"),
        )

        for coordinates, missing_field in cases:
            with self.subTest(missing_field=missing_field):
                self.assert_validation_code(
                    self.make_place(**coordinates),
                    missing_field,
                    "coordinates_incomplete",
                )

    def test_coordinate_precision_may_be_blank_with_coordinates(self) -> None:
        self.make_place(
            latitude=Decimal("50"),
            longitude=Decimal("14"),
        ).full_clean()

    def test_coordinate_precision_requires_coordinates(self) -> None:
        self.assert_validation_code(
            self.make_place(coordinate_precision_m=25),
            "coordinate_precision_m",
            "precision_without_coordinates",
        )

    def test_coordinate_precision_is_valid_with_coordinates(self) -> None:
        self.make_place(
            latitude=Decimal("50"),
            longitude=Decimal("14"),
            coordinate_precision_m=25,
        ).full_clean()

    def test_model_metadata_and_string_representation(self) -> None:
        place = self.make_place(name="Brno")

        self.assertEqual(Place._meta.ordering, ("name",))
        self.assertEqual(Place._meta.verbose_name, "Místo")
        self.assertEqual(Place._meta.verbose_name_plural, "Místa")
        self.assertEqual(str(place), "Brno")


class PlaceDatabaseTests(TestCase):
    """Ověření databázových vazeb a hierarchie míst."""

    @staticmethod
    def create_place(name: str, **overrides) -> Place:
        values = {
            "name": name,
            "normalized_name": name.lower(),
        }
        values.update(overrides)
        return Place.objects.create(**values)

    def assert_parent_error_code(self, place: Place, code: str) -> None:
        with self.assertRaises(ValidationError) as context:
            place.full_clean()

        self.assertIn(
            code,
            {
                error.code
                for error in context.exception.error_dict["parent"]
            },
        )

    def test_places_may_have_identical_names(self) -> None:
        self.create_place("Praha", normalized_name="praha")
        self.create_place("Praha", normalized_name="praha")

        self.assertEqual(
            Place.objects.filter(
                name="Praha",
                normalized_name="praha",
            ).count(),
            2,
        )

    def test_place_type_is_protected_when_used(self) -> None:
        place_type = PlaceType.objects.create(
            code="city",
            name="Město",
        )
        self.create_place("Praha", place_type=place_type)

        with self.assertRaises(ProtectedError):
            place_type.delete()

    def test_parent_deletion_sets_parent_to_null(self) -> None:
        parent = self.create_place("Praha")
        child = self.create_place("Staré Město", parent=parent)

        parent.delete()
        child.refresh_from_db()

        self.assertIsNone(child.parent)

    def test_normal_hierarchy_is_valid(self) -> None:
        country = self.create_place("Česko")
        city = self.create_place("Praha", parent=country)
        district = self.create_place("Staré Město", parent=city)

        district.full_clean()

        self.assertEqual(list(country.children.all()), [city])
        self.assertEqual(list(city.children.all()), [district])

    def test_place_cannot_be_its_own_parent(self) -> None:
        place = self.create_place("Praha")
        place.parent = place

        self.assert_parent_error_code(place, "parent_self")

    def test_two_place_cycle_is_rejected(self) -> None:
        first = self.create_place("První")
        second = self.create_place("Druhé", parent=first)
        first.parent = second

        self.assert_parent_error_code(first, "parent_cycle")

    def test_multistep_cycle_is_rejected(self) -> None:
        first = self.create_place("První")
        second = self.create_place("Druhé", parent=first)
        third = self.create_place("Třetí", parent=second)
        first.parent = third

        self.assert_parent_error_code(first, "parent_cycle")


class PlaceAdminTests(SimpleTestCase):
    """Ověření registrace místa v Django Adminu."""

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(Place))
