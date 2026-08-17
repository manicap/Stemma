from datetime import date

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from people.models import Person

from .models import Place, Residence, ResidenceType


class ResidenceModelTests(SimpleTestCase):
    """Ověření struktury, metadat a čisté modelové validace bydliště."""

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
        "date_precision",
        "date_qualifier",
        "start_year",
        "start_month",
        "start_day",
        "end_year",
        "end_month",
        "end_day",
        "original_date_text",
        "date_note",
        "sort_date",
        "sort_date_end",
    }

    @staticmethod
    def make_residence(**overrides) -> Residence:
        values = {
            "person": Person(first_name="Jan", last_name="Novák"),
            "residence_type": ResidenceType(
                code="primary",
                name="Hlavní bydliště",
            ),
            "address_text": "Pražská 127",
        }
        values.update(overrides)
        return Residence(**values)

    def assert_validation_code(
        self,
        residence: Residence,
        field_name: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            residence.full_clean(exclude=("person", "residence_type"))

        self.assertIn(field_name, context.exception.error_dict)
        self.assertIn(
            code,
            {
                error.code
                for error in context.exception.error_dict[field_name]
            },
        )

    def test_model_is_concrete_and_uses_mixins_in_exact_order(self) -> None:
        self.assertFalse(Residence._meta.abstract)
        self.assertEqual(
            Residence.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                VerifiableModel,
                AuthoredModel,
                LifecycleModel,
                PartialDateModel,
                models.Model,
            ),
        )
        self.assertIs(apps.get_model("places", "Residence"), Residence)

    def test_model_has_only_approved_own_fields(self) -> None:
        own_fields = tuple(
            field.name
            for field in Residence._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            own_fields,
            (
                "person",
                "residence_type",
                "place",
                "address_text",
                "note",
            ),
        )

    def test_inherited_fields_are_present_once(self) -> None:
        field_names = [field.name for field in Residence._meta.local_fields]

        self.assertTrue(self.inherited_field_names <= set(field_names))
        for field_name in self.inherited_field_names:
            with self.subTest(field_name=field_name):
                self.assertEqual(field_names.count(field_name), 1)

    def test_foreign_keys_have_approved_contract(self) -> None:
        expected = {
            "person": (Person, "residences", False, False),
            "residence_type": (
                ResidenceType,
                "residences",
                False,
                False,
            ),
            "place": (Place, "residences", True, True),
        }

        for field_name, (
            target,
            related_name,
            null,
            blank,
        ) in expected.items():
            with self.subTest(field_name=field_name):
                field = Residence._meta.get_field(field_name)
                self.assertIsInstance(field, models.ForeignKey)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertEqual(field.remote_field.related_name, related_name)
                self.assertIs(field.null, null)
                self.assertIs(field.blank, blank)

    def test_text_fields_have_approved_contract(self) -> None:
        address_text = Residence._meta.get_field("address_text")
        note = Residence._meta.get_field("note")

        self.assertIsInstance(address_text, models.CharField)
        self.assertEqual(address_text.max_length, 500)
        self.assertTrue(address_text.blank)
        self.assertFalse(address_text.null)
        self.assertIsInstance(note, models.TextField)
        self.assertTrue(note.blank)
        self.assertFalse(note.null)

    def test_metadata_constraints_and_indexes(self) -> None:
        self.assertEqual(Residence._meta.verbose_name, "Bydliště")
        self.assertEqual(Residence._meta.verbose_name_plural, "Bydliště")
        self.assertEqual(
            Residence._meta.ordering,
            (
                "person_id",
                "sort_date",
                "sort_date_end",
                "residence_type__sort_order",
                "pk",
            ),
        )
        self.assertEqual(Residence._meta.constraints, [])
        self.assertEqual(Residence._meta.indexes, [])

    def test_location_accepts_place_only(self) -> None:
        residence = self.make_residence(
            place=Place(
                pk=1,
                name="Chomutov",
                normalized_name="chomutov",
            ),
            address_text="",
        )

        residence.full_clean(
            exclude=("person", "residence_type", "place")
        )

    def test_location_accepts_address_only(self) -> None:
        self.make_residence().full_clean(
            exclude=("person", "residence_type")
        )

    def test_location_accepts_place_and_address(self) -> None:
        residence = self.make_residence(
            place=Place(
                pk=1,
                name="Chomutov",
                normalized_name="chomutov",
            )
        )

        residence.full_clean(
            exclude=("person", "residence_type", "place")
        )

    def test_location_rejects_both_empty(self) -> None:
        self.assert_validation_code(
            self.make_residence(address_text=""),
            "address_text",
            "residence_location_required",
        )

    def test_location_rejects_whitespace_only_address(self) -> None:
        self.assert_validation_code(
            self.make_residence(address_text=" \t\n "),
            "address_text",
            "residence_location_required",
        )

    def test_partial_date_unknown_is_default(self) -> None:
        residence = self.make_residence()

        residence.full_clean(exclude=("person", "residence_type"))

        self.assertEqual(residence.date_precision, DatePrecision.UNKNOWN)
        self.assertEqual(residence.date_qualifier, DateQualifier.NONE)
        self.assertIsNone(residence.sort_date)
        self.assertIsNone(residence.sort_date_end)

    def test_partial_date_year_is_derived(self) -> None:
        residence = self.make_residence(
            date_precision=DatePrecision.YEAR,
            start_year=1901,
        )

        residence.full_clean(exclude=("person", "residence_type"))

        self.assertEqual(residence.sort_date, date(1901, 1, 1))
        self.assertEqual(residence.sort_date_end, date(1901, 12, 31))

    def test_partial_date_range_is_derived(self) -> None:
        residence = self.make_residence(
            date_precision=DatePrecision.RANGE,
            start_year=1901,
            end_year=1903,
        )

        residence.full_clean(exclude=("person", "residence_type"))

        self.assertEqual(residence.sort_date, date(1901, 1, 1))
        self.assertEqual(residence.sort_date_end, date(1903, 12, 31))

    def test_partial_date_validation_error_is_preserved(self) -> None:
        self.assert_validation_code(
            self.make_residence(
                date_precision=DatePrecision.EXACT,
                start_year=1901,
            ),
            "start_month",
            "missing_month",
        )

    def test_string_representation_for_place_only(self) -> None:
        residence = self.make_residence(
            place=Place(name="Chomutov", normalized_name="chomutov"),
            address_text="",
        )

        self.assertEqual(
            str(residence),
            "Novák Jan – Hlavní bydliště – Chomutov",
        )

    def test_string_representation_for_address_only(self) -> None:
        self.assertEqual(
            str(self.make_residence()),
            "Novák Jan – Hlavní bydliště – Pražská 127",
        )

    def test_string_representation_for_place_and_address(self) -> None:
        residence = self.make_residence(
            place=Place(name="Chomutov", normalized_name="chomutov")
        )

        self.assertEqual(
            str(residence),
            "Novák Jan – Hlavní bydliště – Chomutov, Pražská 127",
        )

    def test_string_representation_defends_against_missing_location(
        self,
    ) -> None:
        residence = self.make_residence(address_text="")

        self.assertEqual(
            str(residence),
            "Novák Jan – Hlavní bydliště – Neznámá lokalita",
        )


class ResidenceDatabaseTests(TestCase):
    """Ověření databázového chování a společných mixinů bydliště."""

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Jan",
            last_name="Novák",
        )
        self.residence_type = ResidenceType.objects.create(
            code="primary-test",
            name="Hlavní bydliště",
        )
        self.place = Place.objects.create(
            name="Chomutov",
            normalized_name="chomutov",
        )

    def create_residence(self, **overrides) -> Residence:
        values = {
            "person": self.person,
            "residence_type": self.residence_type,
            "place": self.place,
        }
        values.update(overrides)
        residence = Residence(**values)
        residence.full_clean()
        residence.save()
        return residence

    def test_mixin_defaults_and_timestamps_are_persisted(self) -> None:
        residence = self.create_residence()

        self.assertEqual(residence.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            residence.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertIsNone(residence.created_by)
        self.assertIsNone(residence.archived_at)
        self.assertIsNone(residence.deleted_at)
        self.assertEqual(residence.date_precision, DatePrecision.UNKNOWN)
        self.assertIsNotNone(residence.created_at)
        self.assertIsNotNone(residence.updated_at)

    def test_save_does_not_normalize_address_text(self) -> None:
        residence = self.create_residence(
            place=None,
            address_text="  historická adresa  ",
        )
        residence.refresh_from_db()

        self.assertEqual(residence.address_text, "  historická adresa  ")

    def test_archiving_does_not_change_residence_period(self) -> None:
        residence = self.create_residence(
            date_precision=DatePrecision.YEAR,
            start_year=1901,
        )
        original_period = (
            residence.start_year,
            residence.sort_date,
            residence.sort_date_end,
        )

        residence.archived_at = timezone.now()
        residence.save(update_fields=("archived_at",))
        residence.refresh_from_db()

        self.assertEqual(
            (
                residence.start_year,
                residence.sort_date,
                residence.sort_date_end,
            ),
            original_period,
        )

    def test_soft_delete_does_not_change_residence_period(self) -> None:
        residence = self.create_residence(
            date_precision=DatePrecision.YEAR,
            start_year=1901,
        )
        original_period = (
            residence.start_year,
            residence.sort_date,
            residence.sort_date_end,
        )

        residence.deleted_at = timezone.now()
        residence.save(update_fields=("deleted_at",))
        residence.refresh_from_db()

        self.assertEqual(
            (
                residence.start_year,
                residence.sort_date,
                residence.sort_date_end,
            ),
            original_period,
        )

    def test_person_is_protected_from_physical_deletion(self) -> None:
        self.create_residence()

        with self.assertRaises(ProtectedError):
            self.person.delete()

    def test_residence_type_is_protected_from_physical_deletion(self) -> None:
        self.create_residence()

        with self.assertRaises(ProtectedError):
            self.residence_type.delete()

    def test_place_is_protected_from_physical_deletion(self) -> None:
        self.create_residence()

        with self.assertRaises(ProtectedError):
            self.place.delete()

    def test_multiple_periods_for_same_person_type_and_place_are_allowed(
        self,
    ) -> None:
        self.create_residence(
            date_precision=DatePrecision.YEAR,
            start_year=1901,
        )
        self.create_residence(
            date_precision=DatePrecision.YEAR,
            start_year=1902,
        )

        self.assertEqual(Residence.objects.count(), 2)

    def test_user_defined_residence_type_is_allowed(self) -> None:
        user_type = ResidenceType.objects.create(
            code="user-defined",
            name="Uživatelský typ",
            is_system=False,
        )

        residence = self.create_residence(residence_type=user_type)

        self.assertEqual(residence.residence_type, user_type)

    def test_inactive_residence_type_is_allowed_by_model(self) -> None:
        inactive_type = ResidenceType.objects.create(
            code="inactive",
            name="Neaktivní typ",
            is_active=False,
        )

        residence = self.create_residence(residence_type=inactive_type)

        self.assertEqual(residence.residence_type, inactive_type)


class ResidenceAdminTests(SimpleTestCase):
    """Ověření fail-closed hranice bydliště v Django Adminu."""

    def test_model_is_not_registered(self) -> None:
        self.assertFalse(admin.site.is_registered(Residence))
