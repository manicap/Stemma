from decimal import Decimal

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)

from .choices import GraveSiteStatus
from .models import GraveSite, GraveSiteType, Place


class GraveSiteModelTests(SimpleTestCase):
    """Ověření struktury, metadat a čisté validace GraveSite."""

    inherited_field_names = {
        "id",
        "created_at",
        "updated_at",
        "access_level",
        "verification_status",
        "created_by",
        "archived_at",
        "archived_by",
        "archive_reason",
        "deleted_at",
        "deleted_by",
        "deletion_reason",
    }

    @staticmethod
    def make_grave_site(**overrides: object) -> GraveSite:
        values = {
            "grave_site_type": GraveSiteType(
                pk=1,
                code="grave",
                name="Hrob",
            ),
            "location_text": "Historická lokalita",
        }
        values.update(overrides)
        return GraveSite(**values)

    @staticmethod
    def validation_codes(
        grave_site: GraveSite,
        *,
        exclude: tuple[str, ...] = ("grave_site_type", "place"),
    ) -> dict[str, set[str | None]]:
        try:
            grave_site.full_clean(exclude=exclude)
        except ValidationError as error:
            return {
                field_name: {
                    field_error.code for field_error in field_errors
                }
                for field_name, field_errors in error.error_dict.items()
            }
        return {}

    def test_model_is_concrete_and_uses_exact_mixins(self) -> None:
        self.assertFalse(GraveSite._meta.abstract)
        self.assertEqual(
            GraveSite.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                VerifiableModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertNotIn(PartialDateModel, GraveSite.__bases__)
        self.assertIs(apps.get_model("places", "GraveSite"), GraveSite)

    def test_model_has_only_approved_own_fields(self) -> None:
        own_fields = tuple(
            field.name
            for field in GraveSite._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            own_fields,
            (
                "grave_site_type",
                "status",
                "place",
                "location_text",
                "cemetery_name",
                "section",
                "row",
                "grave_number",
                "inscription",
                "latitude",
                "longitude",
                "note",
            ),
        )

    def test_inherited_fields_are_present_once_without_partial_date(self) -> None:
        field_names = [
            field.name for field in GraveSite._meta.local_fields
        ]

        self.assertTrue(self.inherited_field_names <= set(field_names))
        for field_name in self.inherited_field_names:
            with self.subTest(field_name=field_name):
                self.assertEqual(field_names.count(field_name), 1)
        for forbidden_field in (
            "date_precision",
            "start_year",
            "end_year",
            "sort_date",
            "sort_date_end",
        ):
            self.assertNotIn(forbidden_field, field_names)

    def test_foreign_keys_have_exact_contract(self) -> None:
        expectations = {
            "grave_site_type": (
                GraveSiteType,
                "grave_sites",
                False,
                False,
            ),
            "place": (Place, "grave_sites", True, True),
        }

        for field_name, (
            target,
            related_name,
            null,
            blank,
        ) in expectations.items():
            with self.subTest(field_name=field_name):
                field = GraveSite._meta.get_field(field_name)
                self.assertIsInstance(field, models.ForeignKey)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertEqual(field.remote_field.related_name, related_name)
                self.assertIs(field.null, null)
                self.assertIs(field.blank, blank)

    def test_status_field_has_exact_contract(self) -> None:
        status = GraveSite._meta.get_field("status")

        self.assertIsInstance(status, models.CharField)
        self.assertEqual(status.max_length, 20)
        self.assertEqual(status.choices, GraveSiteStatus.choices)
        self.assertEqual(status.default, GraveSiteStatus.UNKNOWN)

    def test_text_fields_have_exact_contract(self) -> None:
        char_fields = {
            "location_text": 500,
            "cemetery_name": 255,
            "section": 100,
            "row": 100,
            "grave_number": 100,
        }
        for field_name, max_length in char_fields.items():
            with self.subTest(field_name=field_name):
                field = GraveSite._meta.get_field(field_name)
                self.assertIsInstance(field, models.CharField)
                self.assertEqual(field.max_length, max_length)
                self.assertTrue(field.blank)
                self.assertFalse(field.null)

        for field_name in ("inscription", "note"):
            with self.subTest(field_name=field_name):
                field = GraveSite._meta.get_field(field_name)
                self.assertIsInstance(field, models.TextField)
                self.assertTrue(field.blank)
                self.assertFalse(field.null)

    def test_coordinate_fields_have_exact_contract(self) -> None:
        for field_name in ("latitude", "longitude"):
            with self.subTest(field_name=field_name):
                field = GraveSite._meta.get_field(field_name)
                self.assertIsInstance(field, models.DecimalField)
                self.assertEqual(field.max_digits, 9)
                self.assertEqual(field.decimal_places, 6)
                self.assertTrue(field.null)
                self.assertTrue(field.blank)

    def test_metadata_has_no_constraints_or_explicit_indexes(self) -> None:
        self.assertEqual(
            GraveSite._meta.verbose_name,
            "Hrobové nebo pamětní místo",
        )
        self.assertEqual(
            GraveSite._meta.verbose_name_plural,
            "Hrobová a pamětní místa",
        )
        self.assertEqual(
            GraveSite._meta.ordering,
            (
                "cemetery_name",
                "section",
                "row",
                "grave_number",
                "pk",
            ),
        )
        self.assertEqual(GraveSite._meta.constraints, [])
        self.assertEqual(GraveSite._meta.indexes, [])

    def test_all_approved_location_variants_are_valid(self) -> None:
        variants = (
            {
                "place": Place(
                    pk=1,
                    name="Chomutov",
                    normalized_name="chomutov",
                ),
                "location_text": "",
            },
            {"location_text": "U kostela"},
            {"location_text": "", "cemetery_name": "Městský hřbitov"},
            {
                "location_text": "",
                "latitude": Decimal("50.000000"),
                "longitude": Decimal("14.000000"),
            },
            {
                "place": Place(
                    pk=1,
                    name="Chomutov",
                    normalized_name="chomutov",
                ),
                "location_text": "U severní zdi",
                "cemetery_name": "Městský hřbitov",
                "latitude": Decimal("50.000000"),
                "longitude": Decimal("14.000000"),
            },
        )

        for index, values in enumerate(variants):
            with self.subTest(index=index):
                self.assertEqual(
                    self.validation_codes(
                        self.make_grave_site(**values)
                    ),
                    {},
                )

    def test_missing_or_whitespace_location_is_rejected(self) -> None:
        for values in (
            {"location_text": ""},
            {
                "location_text": " \t ",
                "cemetery_name": " \n ",
            },
        ):
            with self.subTest(values=values):
                codes = self.validation_codes(
                    self.make_grave_site(**values)
                )
                self.assertIn(
                    "grave_site_location_required",
                    codes["location_text"],
                )

    def test_incomplete_coordinates_use_missing_field_and_stable_code(
        self,
    ) -> None:
        variants = (
            (
                {"latitude": Decimal("50"), "longitude": None},
                "longitude",
            ),
            (
                {"latitude": None, "longitude": Decimal("14")},
                "latitude",
            ),
        )
        for coordinates, missing_field in variants:
            with self.subTest(missing_field=missing_field):
                codes = self.validation_codes(
                    self.make_grave_site(
                        cemetery_name="Hřbitov",
                        **coordinates,
                    )
                )
                self.assertIn(
                    "grave_site_coordinates_incomplete",
                    codes[missing_field],
                )

    def test_coordinate_boundaries_are_valid(self) -> None:
        for latitude, longitude in (
            (Decimal("-90"), Decimal("-180")),
            (Decimal("90"), Decimal("180")),
        ):
            with self.subTest(latitude=latitude, longitude=longitude):
                self.assertEqual(
                    self.validation_codes(
                        self.make_grave_site(
                            location_text="",
                            latitude=latitude,
                            longitude=longitude,
                        )
                    ),
                    {},
                )

    def test_out_of_range_coordinates_use_stable_codes(self) -> None:
        variants = (
            (
                {"latitude": Decimal("-90.000001")},
                "latitude",
                "grave_site_latitude_out_of_range",
            ),
            (
                {"latitude": Decimal("90.000001")},
                "latitude",
                "grave_site_latitude_out_of_range",
            ),
            (
                {"longitude": Decimal("-180.000001")},
                "longitude",
                "grave_site_longitude_out_of_range",
            ),
            (
                {"longitude": Decimal("180.000001")},
                "longitude",
                "grave_site_longitude_out_of_range",
            ),
        )
        for coordinates, field_name, code in variants:
            with self.subTest(field_name=field_name, coordinates=coordinates):
                values = {
                    "latitude": Decimal("50"),
                    "longitude": Decimal("14"),
                }
                values.update(coordinates)
                codes = self.validation_codes(
                    self.make_grave_site(
                        cemetery_name="Hřbitov",
                        **values,
                    )
                )
                self.assertIn(code, codes[field_name])

    def test_status_accepts_only_approved_choices(self) -> None:
        for status in GraveSiteStatus.values:
            with self.subTest(status=status):
                self.assertEqual(
                    self.validation_codes(
                        self.make_grave_site(status=status)
                    ),
                    {},
                )

        codes = self.validation_codes(
            self.make_grave_site(status="relocated")
        )
        self.assertIn("invalid_choice", codes["status"])

    def test_mixin_defaults_are_independent_from_status(self) -> None:
        grave_site = self.make_grave_site()

        self.assertEqual(grave_site.status, GraveSiteStatus.UNKNOWN)
        self.assertEqual(grave_site.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            grave_site.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertIsNone(grave_site.created_by)
        self.assertIsNone(grave_site.archived_at)
        self.assertIsNone(grave_site.archived_by)
        self.assertEqual(grave_site.archive_reason, "")
        self.assertIsNone(grave_site.deleted_at)
        self.assertIsNone(grave_site.deleted_by)
        self.assertEqual(grave_site.deletion_reason, "")

    def test_string_uses_location_priority_identifiers_and_type(self) -> None:
        grave_site = self.make_grave_site(
            cemetery_name="Hřbitov Chomutov",
            location_text="Nižší priorita",
            section="3",
            row="B",
            grave_number="127",
        )

        self.assertEqual(
            str(grave_site),
            "Hřbitov Chomutov – oddíl 3, řada B, hrob 127 – Hrob",
        )

    def test_string_falls_back_through_all_location_variants(self) -> None:
        variants = (
            (
                self.make_grave_site(
                    location_text="Pamětní deska u kostela"
                ),
                "Pamětní deska u kostela – Hrob",
            ),
            (
                self.make_grave_site(
                    location_text="",
                    place=Place(
                        name="Litoměřice",
                        normalized_name="litomerice",
                    ),
                ),
                "Litoměřice – Hrob",
            ),
            (
                self.make_grave_site(
                    location_text="",
                    latitude=Decimal("50.100000"),
                    longitude=Decimal("14.200000"),
                ),
                "50.100000, 14.200000 – Hrob",
            ),
            (
                GraveSite(),
                "Hrobové nebo pamětní místo",
            ),
        )

        for grave_site, expected in variants:
            with self.subTest(expected=expected):
                self.assertEqual(str(grave_site), expected)


class GraveSiteDatabaseTests(TestCase):
    """Ověření databázového chování, lifecycle a PROTECT."""

    def setUp(self) -> None:
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Chomutov",
            normalized_name="chomutov",
        )

    def create_grave_site(self, **overrides: object) -> GraveSite:
        values = {
            "grave_site_type": self.grave_site_type,
            "location_text": "Historická lokalita",
        }
        values.update(overrides)
        grave_site = GraveSite(**values)
        grave_site.full_clean()
        grave_site.save()
        return grave_site

    def test_save_preserves_text_and_allows_alphanumeric_identifiers(
        self,
    ) -> None:
        grave_site = self.create_grave_site(
            location_text="  Historická lokalita  ",
            section="III/A",
            row="B-2",
            grave_number="127a/1",
            inscription="Přepis nápisu",
            note="Interní poznámka",
        )
        grave_site.refresh_from_db()

        self.assertEqual(
            grave_site.location_text,
            "  Historická lokalita  ",
        )
        self.assertEqual(grave_site.section, "III/A")
        self.assertEqual(grave_site.row, "B-2")
        self.assertEqual(grave_site.grave_number, "127a/1")
        self.assertEqual(grave_site.inscription, "Přepis nápisu")
        self.assertEqual(grave_site.note, "Interní poznámka")
        self.assertIsNotNone(grave_site.created_at)
        self.assertIsNotNone(grave_site.updated_at)

    def test_status_and_lifecycle_changes_are_independent(self) -> None:
        grave_site = self.create_grave_site()

        grave_site.status = GraveSiteStatus.DESTROYED
        grave_site.full_clean()
        grave_site.save(update_fields=("status",))
        grave_site.refresh_from_db()
        self.assertIsNone(grave_site.archived_at)
        self.assertIsNone(grave_site.deleted_at)

        now = timezone.now()
        GraveSite.objects.filter(pk=grave_site.pk).update(archived_at=now)
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.status, GraveSiteStatus.DESTROYED)
        self.assertEqual(grave_site.archived_at, now)
        self.assertIsNone(grave_site.deleted_at)

        GraveSite.objects.filter(pk=grave_site.pk).update(deleted_at=now)
        grave_site.refresh_from_db()
        self.assertEqual(grave_site.status, GraveSiteStatus.DESTROYED)
        self.assertEqual(grave_site.archived_at, now)
        self.assertEqual(grave_site.deleted_at, now)

    def test_model_allows_inactive_type(self) -> None:
        inactive_type = GraveSiteType.objects.create(
            code="inactive_grave_type",
            name="Neaktivní typ",
            is_active=False,
        )

        grave_site = self.create_grave_site(
            grave_site_type=inactive_type,
        )

        self.assertEqual(grave_site.grave_site_type, inactive_type)

    def test_model_allows_user_defined_type(self) -> None:
        user_type = GraveSiteType.objects.create(
            code="user_grave_type",
            name="Uživatelský typ",
        )

        grave_site = self.create_grave_site(grave_site_type=user_type)

        self.assertFalse(user_type.is_system)
        self.assertEqual(grave_site.grave_site_type, user_type)

    def test_referenced_type_and_place_are_protected(self) -> None:
        protected_type = GraveSiteType.objects.create(
            code="protected_grave_type",
            name="Chráněný typ",
        )
        protected_place = Place.objects.create(
            name="Chráněné místo",
            normalized_name="chranene misto",
        )
        self.create_grave_site(
            grave_site_type=protected_type,
            place=protected_place,
        )

        for protected_object in (protected_type, protected_place):
            with self.subTest(model=type(protected_object).__name__):
                with self.assertRaises(ProtectedError):
                    with transaction.atomic():
                        protected_object.delete()

    def test_duplicate_locations_are_allowed(self) -> None:
        first = self.create_grave_site(
            cemetery_name="Městský hřbitov",
            section="3",
            row="B",
            grave_number="127",
        )
        second = self.create_grave_site(
            cemetery_name="Městský hřbitov",
            section="3",
            row="B",
            grave_number="127",
        )

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(GraveSite.objects.count(), 2)

    def test_created_by_is_optional_and_can_reference_current_user(
        self,
    ) -> None:
        without_author = self.create_grave_site()
        actor = get_user_model().objects.create_user(username="grave-author")
        with_author = self.create_grave_site(
            location_text="Druhá lokalita",
            created_by=actor,
        )

        self.assertIsNone(without_author.created_by)
        self.assertEqual(with_author.created_by, actor)


class GraveSiteAdminTests(SimpleTestCase):
    """Ověření fail-closed hranice GraveSite v Django Adminu."""

    def test_model_is_not_registered(self) -> None:
        self.assertFalse(admin.site.is_registered(GraveSite))
