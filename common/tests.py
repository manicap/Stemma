from datetime import date
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, models
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import isolate_apps

from .choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    Gender,
    VerificationStatus,
)
from .models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from .partial_dates import (
    PartialDateValue,
    derive_sort_dates,
    validate_partial_date,
)


def create_partial_date_test_model() -> type[PartialDateModel]:
    """Create a concrete partial-date model in an isolated app registry."""

    class ConcretePartialDate(PartialDateModel):
        class Meta:
            app_label = "common"

    return ConcretePartialDate


class FixedChoicesTests(SimpleTestCase):
    """Test stability of shared fixed choices."""

    choice_cases = (
        (
            Gender,
            [
                ("male", "Muž"),
                ("female", "Žena"),
                ("unknown", "Neznámé"),
            ],
        ),
        (
            AccessLevel,
            [
                ("public", "Veřejné"),
                ("authenticated", "Pouze přihlášení"),
                ("restricted", "Omezené"),
                ("admin_only", "Pouze správce"),
            ],
        ),
        (
            VerificationStatus,
            [
                ("verified", "Ověřeno"),
                ("probable", "Pravděpodobné"),
                ("uncertain", "Nejisté"),
                ("disputed", "Sporné"),
                ("unconfirmed", "Nepotvrzené"),
            ],
        ),
        (
            DatePrecision,
            [
                ("exact", "Přesné datum"),
                ("month", "Měsíc a rok"),
                ("year", "Pouze rok"),
                ("range", "Rozmezí"),
                ("unknown", "Neznámé datum"),
            ],
        ),
        (
            DateQualifier,
            [
                ("none", "Bez kvalifikátoru"),
                ("approximate", "Přibližně"),
                ("before", "Před"),
                ("after", "Po"),
            ],
        ),
    )

    def test_technical_values(self):
        for choice_type, expected_choices in self.choice_cases:
            with self.subTest(choice_type=choice_type.__name__):
                expected_values = [value for value, _label in expected_choices]

                self.assertEqual(choice_type.values, expected_values)

    def test_czech_labels(self):
        for choice_type, expected_choices in self.choice_cases:
            with self.subTest(choice_type=choice_type.__name__):
                expected_labels = [label for _value, label in expected_choices]

                self.assertEqual(choice_type.labels, expected_labels)

    def test_choices_order(self):
        for choice_type, expected_choices in self.choice_cases:
            with self.subTest(choice_type=choice_type.__name__):
                self.assertEqual(choice_type.choices, expected_choices)

    def test_values_are_unique(self):
        for choice_type, _expected_choices in self.choice_cases:
            with self.subTest(choice_type=choice_type.__name__):
                self.assertEqual(
                    len(choice_type.values),
                    len(set(choice_type.values)),
                )


class AbstractModelsTests(SimpleTestCase):
    """Test metadata of shared abstract models."""

    abstract_models = (
        TimestampedModel,
        AuthoredModel,
        AccessControlledModel,
        VerifiableModel,
        LifecycleModel,
        PartialDateModel,
        LookupModel,
    )

    def test_models_are_abstract(self):
        for abstract_model in self.abstract_models:
            with self.subTest(model=abstract_model.__name__):
                self.assertTrue(abstract_model._meta.abstract)

    def test_timestamped_model_fields(self):
        self.assertEqual(
            [field.name for field in TimestampedModel._meta.local_fields],
            ["created_at", "updated_at"],
        )

        created_at = TimestampedModel._meta.get_field("created_at")
        updated_at = TimestampedModel._meta.get_field("updated_at")

        self.assertIsInstance(created_at, models.DateTimeField)
        self.assertTrue(created_at.auto_now_add)
        self.assertIsInstance(updated_at, models.DateTimeField)
        self.assertTrue(updated_at.auto_now)

    def test_access_controlled_model_field(self):
        self.assertEqual(
            [field.name for field in AccessControlledModel._meta.local_fields],
            ["access_level"],
        )

        access_level = AccessControlledModel._meta.get_field("access_level")

        self.assertIsInstance(access_level, models.CharField)
        self.assertEqual(access_level.max_length, 20)
        self.assertEqual(access_level.choices, AccessLevel.choices)
        self.assertEqual(access_level.default, AccessLevel.PUBLIC)

    def test_authored_model_field(self):
        self.assertEqual(
            [field.name for field in AuthoredModel._meta.local_fields],
            ["created_by"],
        )

        created_by = AuthoredModel._meta.get_field("created_by")

        self.assertIsInstance(created_by, models.ForeignKey)
        self.assertEqual(created_by.remote_field.model, settings.AUTH_USER_MODEL)
        self.assertIs(created_by.remote_field.on_delete, models.SET_NULL)
        self.assertTrue(created_by.null)
        self.assertTrue(created_by.blank)
        self.assertEqual(created_by.remote_field.related_name, "+")

    def test_verifiable_model_field(self):
        self.assertEqual(
            [field.name for field in VerifiableModel._meta.local_fields],
            ["verification_status"],
        )

        verification_status = VerifiableModel._meta.get_field(
            "verification_status"
        )

        self.assertIsInstance(verification_status, models.CharField)
        self.assertEqual(verification_status.max_length, 20)
        self.assertEqual(
            verification_status.choices,
            VerificationStatus.choices,
        )
        self.assertEqual(
            verification_status.default,
            VerificationStatus.UNCONFIRMED,
        )

    def test_lifecycle_model_fields(self):
        self.assertEqual(
            [field.name for field in LifecycleModel._meta.local_fields],
            [
                "archived_at",
                "archived_by",
                "archive_reason",
                "deleted_at",
                "deleted_by",
                "deletion_reason",
            ],
        )

        for field_name in ("archived_at", "deleted_at"):
            with self.subTest(field=field_name):
                date_field = LifecycleModel._meta.get_field(field_name)
                self.assertIsInstance(date_field, models.DateTimeField)
                self.assertTrue(date_field.null)
                self.assertTrue(date_field.blank)
                self.assertFalse(date_field.editable)

        for field_name in ("archived_by", "deleted_by"):
            with self.subTest(field=field_name):
                user_field = LifecycleModel._meta.get_field(field_name)
                self.assertIsInstance(user_field, models.ForeignKey)
                self.assertEqual(
                    user_field.remote_field.model,
                    settings.AUTH_USER_MODEL,
                )
                self.assertIs(user_field.remote_field.on_delete, models.SET_NULL)
                self.assertTrue(user_field.null)
                self.assertTrue(user_field.blank)
                self.assertEqual(user_field.remote_field.related_name, "+")

        for field_name in ("archive_reason", "deletion_reason"):
            with self.subTest(field=field_name):
                reason_field = LifecycleModel._meta.get_field(field_name)
                self.assertIsInstance(reason_field, models.TextField)
                self.assertTrue(reason_field.blank)
                self.assertFalse(reason_field.null)

    def test_lookup_model_fields(self):
        self.assertEqual(
            [field.name for field in LookupModel._meta.local_fields],
            [
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
            ],
        )

        code = LookupModel._meta.get_field("code")
        self.assertIsInstance(code, models.CharField)
        self.assertEqual(code.max_length, 50)
        self.assertTrue(code.unique)

        name = LookupModel._meta.get_field("name")
        self.assertIsInstance(name, models.CharField)
        self.assertEqual(name.max_length, 100)

        description = LookupModel._meta.get_field("description")
        self.assertIsInstance(description, models.TextField)
        self.assertTrue(description.blank)
        self.assertFalse(description.null)

        sort_order = LookupModel._meta.get_field("sort_order")
        self.assertIsInstance(sort_order, models.PositiveIntegerField)
        self.assertEqual(sort_order.default, 0)

        is_active = LookupModel._meta.get_field("is_active")
        self.assertIsInstance(is_active, models.BooleanField)
        self.assertIs(is_active.default, True)

        is_system = LookupModel._meta.get_field("is_system")
        self.assertIsInstance(is_system, models.BooleanField)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_partial_date_model_fields(self):
        self.assertEqual(
            [field.name for field in PartialDateModel._meta.local_fields],
            [
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
            ],
        )

        date_precision = PartialDateModel._meta.get_field("date_precision")
        self.assertIsInstance(date_precision, models.CharField)
        self.assertEqual(date_precision.max_length, 10)
        self.assertEqual(date_precision.choices, DatePrecision.choices)
        self.assertEqual(date_precision.default, DatePrecision.UNKNOWN)

        date_qualifier = PartialDateModel._meta.get_field("date_qualifier")
        self.assertIsInstance(date_qualifier, models.CharField)
        self.assertEqual(date_qualifier.max_length, 12)
        self.assertEqual(date_qualifier.choices, DateQualifier.choices)
        self.assertEqual(date_qualifier.default, DateQualifier.NONE)

        date_part_fields = (
            "start_year",
            "start_month",
            "start_day",
            "end_year",
            "end_month",
            "end_day",
        )
        for field_name in date_part_fields:
            with self.subTest(field=field_name):
                date_part = PartialDateModel._meta.get_field(field_name)
                self.assertIsInstance(
                    date_part,
                    models.PositiveSmallIntegerField,
                )
                self.assertTrue(date_part.null)
                self.assertTrue(date_part.blank)

        original_date_text = PartialDateModel._meta.get_field(
            "original_date_text"
        )
        self.assertIsInstance(original_date_text, models.CharField)
        self.assertEqual(original_date_text.max_length, 255)
        self.assertTrue(original_date_text.blank)
        self.assertFalse(original_date_text.null)

        date_note = PartialDateModel._meta.get_field("date_note")
        self.assertIsInstance(date_note, models.TextField)
        self.assertTrue(date_note.blank)
        self.assertFalse(date_note.null)

        sort_date = PartialDateModel._meta.get_field("sort_date")
        self.assertIsInstance(sort_date, models.DateField)
        self.assertTrue(sort_date.null)
        self.assertTrue(sort_date.blank)
        self.assertFalse(sort_date.editable)
        self.assertTrue(sort_date.db_index)

        sort_date_end = PartialDateModel._meta.get_field("sort_date_end")
        self.assertIsInstance(sort_date_end, models.DateField)
        self.assertTrue(sort_date_end.null)
        self.assertTrue(sort_date_end.blank)
        self.assertFalse(sort_date_end.editable)
        self.assertFalse(sort_date_end.db_index)

    def test_lookup_model_ordering(self):
        self.assertEqual(
            LookupModel._meta.ordering,
            ("sort_order", "name", "code"),
        )

    def test_abstract_models_are_not_registered_as_concrete_models(self):
        registered_models = set(apps.get_models())

        for abstract_model in self.abstract_models:
            with self.subTest(model=abstract_model.__name__):
                self.assertNotIn(abstract_model, registered_models)


class PartialDateValidationTests(SimpleTestCase):
    """Test valid and invalid combinations of partial-date values."""

    def assert_validation_code(
        self,
        value: PartialDateValue,
        field: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            validate_partial_date(value)

        self.assertIn(field, context.exception.error_dict)
        self.assertIn(
            code,
            [error.code for error in context.exception.error_dict[field]],
        )

    def test_valid_precisions_and_ranges(self):
        valid_values = (
            (
                "exact",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1985,
                    start_month=7,
                    start_day=14,
                ),
            ),
            (
                "leap_day",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=2000,
                    start_month=2,
                    start_day=29,
                ),
            ),
            (
                "month",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                ),
            ),
            (
                "year",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=1840,
                ),
            ),
            (
                "minimum_year",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=1,
                ),
            ),
            (
                "maximum_year",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=9999,
                ),
            ),
            (
                "unknown",
                PartialDateValue(
                    DatePrecision.UNKNOWN,
                    DateQualifier.NONE,
                ),
            ),
            (
                "year_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    end_year=1850,
                ),
            ),
            (
                "month_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                    end_year=1850,
                    end_month=8,
                ),
            ),
            (
                "exact_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                    start_day=12,
                    end_year=1850,
                    end_month=8,
                    end_day=20,
                ),
            ),
            (
                "mixed_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                    start_day=12,
                    end_year=1850,
                    end_month=8,
                ),
            ),
            (
                "reverse_mixed_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    end_year=1850,
                    end_month=8,
                    end_day=12,
                ),
            ),
        )

        for name, value in valid_values:
            with self.subTest(case=name):
                validate_partial_date(value)

    def test_valid_qualifiers(self):
        values = (
            (
                "approximate_exact",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.APPROXIMATE,
                    start_year=1900,
                    start_month=5,
                    start_day=10,
                ),
            ),
            (
                "approximate_year",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.APPROXIMATE,
                    start_year=1900,
                ),
            ),
            (
                "approximate_month",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.APPROXIMATE,
                    start_year=1900,
                    start_month=5,
                ),
            ),
            (
                "approximate_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.APPROXIMATE,
                    start_year=1900,
                    end_year=1910,
                ),
            ),
        )
        for qualifier in (DateQualifier.BEFORE, DateQualifier.AFTER):
            values += (
                (
                    f"{qualifier}_exact",
                    PartialDateValue(
                        DatePrecision.EXACT,
                        qualifier,
                        start_year=1900,
                        start_month=5,
                        start_day=10,
                    ),
                ),
                (
                    f"{qualifier}_month",
                    PartialDateValue(
                        DatePrecision.MONTH,
                        qualifier,
                        start_year=1900,
                        start_month=5,
                    ),
                ),
                (
                    f"{qualifier}_year",
                    PartialDateValue(
                        DatePrecision.YEAR,
                        qualifier,
                        start_year=1900,
                    ),
                ),
            )

        for name, value in values:
            with self.subTest(case=name):
                validate_partial_date(value)

    def test_invalid_date_components(self):
        invalid_values = (
            (
                "month_without_year",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_month=3,
                ),
                "start_month",
                "missing_year",
            ),
            (
                "day_without_month",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_day=3,
                ),
                "start_day",
                "missing_month",
            ),
            (
                "day_without_year",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_month=3,
                    start_day=3,
                ),
                "start_day",
                "missing_year",
            ),
            (
                "end_month_without_year",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1900,
                    end_month=3,
                ),
                "end_month",
                "missing_year",
            ),
            (
                "end_day_without_month",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1900,
                    end_year=1901,
                    end_day=3,
                ),
                "end_day",
                "missing_month",
            ),
            (
                "month_zero",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=0,
                ),
                "start_month",
                "invalid_month",
            ),
            (
                "month_thirteen",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=13,
                ),
                "start_month",
                "invalid_month",
            ),
            (
                "year_zero",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=0,
                ),
                "start_year",
                "invalid_year",
            ),
            (
                "year_too_large",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=10000,
                ),
                "start_year",
                "invalid_year",
            ),
            (
                "invalid_day",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                    start_day=31,
                ),
                "start_day",
                "invalid_date",
            ),
            (
                "non_leap_day",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=2,
                    start_day=29,
                ),
                "start_day",
                "invalid_date",
            ),
        )

        for name, value, field, code in invalid_values:
            with self.subTest(case=name):
                self.assert_validation_code(value, field, code)

    def test_invalid_precision_components(self):
        invalid_values = (
            (
                "exact_missing_day",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                ),
                "start_day",
                "missing_day",
            ),
            (
                "month_with_day",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                    start_day=1,
                ),
                "start_day",
                "unexpected_component",
            ),
            (
                "year_with_month",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                ),
                "start_month",
                "unexpected_component",
            ),
            (
                "year_with_day",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_day=1,
                ),
                "start_day",
                "unexpected_component",
            ),
            (
                "end_outside_range",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                    start_day=1,
                    end_year=1901,
                ),
                "end_year",
                "unexpected_component",
            ),
            (
                "range_without_start",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    end_year=1901,
                ),
                "start_year",
                "missing_range_start",
            ),
            (
                "range_without_end",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1900,
                ),
                "end_year",
                "missing_range_end",
            ),
            (
                "range_end_before_start",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1901,
                    end_year=1900,
                ),
                "end_year",
                "range_end_before_start",
            ),
            (
                "unknown_with_component",
                PartialDateValue(
                    DatePrecision.UNKNOWN,
                    DateQualifier.NONE,
                    start_year=1900,
                ),
                "start_year",
                "unexpected_component",
            ),
        )

        for name, value, field, code in invalid_values:
            with self.subTest(case=name):
                self.assert_validation_code(value, field, code)

    def test_invalid_qualifiers(self):
        invalid_values = (
            (
                "approximate_unknown",
                DatePrecision.UNKNOWN,
                DateQualifier.APPROXIMATE,
                {},
            ),
            (
                "before_range",
                DatePrecision.RANGE,
                DateQualifier.BEFORE,
                {"start_year": 1900, "end_year": 1901},
            ),
            (
                "after_range",
                DatePrecision.RANGE,
                DateQualifier.AFTER,
                {"start_year": 1900, "end_year": 1901},
            ),
            (
                "before_unknown",
                DatePrecision.UNKNOWN,
                DateQualifier.BEFORE,
                {},
            ),
            (
                "after_unknown",
                DatePrecision.UNKNOWN,
                DateQualifier.AFTER,
                {},
            ),
        )

        for name, precision, qualifier, components in invalid_values:
            with self.subTest(case=name):
                self.assert_validation_code(
                    PartialDateValue(precision, qualifier, **components),
                    "date_qualifier",
                    "invalid_qualifier",
                )


class PartialDateDerivationTests(SimpleTestCase):
    """Test exact technical bounds derived from partial dates."""

    def test_sort_date_derivation(self):
        values = (
            (
                "exact",
                PartialDateValue(
                    DatePrecision.EXACT,
                    DateQualifier.NONE,
                    start_year=1985,
                    start_month=7,
                    start_day=14,
                ),
                date(1985, 7, 14),
                date(1985, 7, 14),
            ),
            (
                "month",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=1900,
                    start_month=4,
                ),
                date(1900, 4, 1),
                date(1900, 4, 30),
            ),
            (
                "leap_february",
                PartialDateValue(
                    DatePrecision.MONTH,
                    DateQualifier.NONE,
                    start_year=2000,
                    start_month=2,
                ),
                date(2000, 2, 1),
                date(2000, 2, 29),
            ),
            (
                "year",
                PartialDateValue(
                    DatePrecision.YEAR,
                    DateQualifier.NONE,
                    start_year=1900,
                ),
                date(1900, 1, 1),
                date(1900, 12, 31),
            ),
            (
                "range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                    end_year=1850,
                    end_month=2,
                ),
                date(1840, 3, 1),
                date(1850, 2, 28),
            ),
            (
                "exact_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    start_month=3,
                    start_day=12,
                    end_year=1850,
                    end_month=8,
                    end_day=20,
                ),
                date(1840, 3, 12),
                date(1850, 8, 20),
            ),
            (
                "mixed_range",
                PartialDateValue(
                    DatePrecision.RANGE,
                    DateQualifier.NONE,
                    start_year=1840,
                    end_year=1850,
                    end_month=8,
                    end_day=20,
                ),
                date(1840, 1, 1),
                date(1850, 8, 20),
            ),
            (
                "unknown",
                PartialDateValue(
                    DatePrecision.UNKNOWN,
                    DateQualifier.NONE,
                ),
                None,
                None,
            ),
        )

        for name, value, expected_start, expected_end in values:
            with self.subTest(case=name):
                self.assertEqual(
                    derive_sort_dates(value),
                    (expected_start, expected_end),
                )

    def test_qualifier_does_not_change_sort_dates(self):
        expected = (date(1900, 1, 1), date(1900, 12, 31))

        for qualifier in (
            DateQualifier.NONE,
            DateQualifier.APPROXIMATE,
            DateQualifier.BEFORE,
            DateQualifier.AFTER,
        ):
            with self.subTest(qualifier=qualifier):
                value = PartialDateValue(
                    DatePrecision.YEAR,
                    qualifier,
                    start_year=1900,
                )
                self.assertEqual(derive_sort_dates(value), expected)

    def test_range_day_without_month_does_not_create_false_date(self):
        invalid_ranges = (
            PartialDateValue(
                DatePrecision.RANGE,
                DateQualifier.NONE,
                start_year=1900,
                start_day=15,
                end_year=1901,
            ),
            PartialDateValue(
                DatePrecision.RANGE,
                DateQualifier.NONE,
                start_year=1900,
                end_year=1901,
                end_day=15,
            ),
        )

        for value in invalid_ranges:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "Den nelze odvodit bez měsíce",
                ):
                    derive_sort_dates(value)


class PartialDateModelBehaviorTests(SimpleTestCase):
    """Test model integration without creating a persistent model."""

    @isolate_apps("common")
    def test_clean_uses_shared_validation_and_sets_sort_dates(self):
        test_model = create_partial_date_test_model()
        instance = test_model(
            date_precision=DatePrecision.MONTH,
            date_qualifier=DateQualifier.NONE,
            start_year=2000,
            start_month=2,
        )

        with patch("common.models.validate_partial_date") as validator:
            instance.clean()

        validator.assert_called_once()
        self.assertEqual(instance.sort_date, date(2000, 2, 1))
        self.assertEqual(instance.sort_date_end, date(2000, 2, 29))

    @isolate_apps("common")
    def test_full_clean_catches_invalid_partial_date(self):
        test_model = create_partial_date_test_model()
        instance = test_model(
            date_precision=DatePrecision.EXACT,
            date_qualifier=DateQualifier.NONE,
            start_year=1900,
            start_month=2,
            start_day=29,
        )

        with self.assertRaises(ValidationError) as context:
            instance.full_clean(
                validate_unique=False,
                validate_constraints=False,
            )

        self.assertIn("start_day", context.exception.error_dict)
        self.assertIn(
            "invalid_date",
            [
                error.code
                for error in context.exception.error_dict["start_day"]
            ],
        )


class PartialDateModelSaveTests(TransactionTestCase):
    """Test persistence-time recalculation on an isolated concrete model."""

    @isolate_apps("common")
    def test_save_recalculates_without_full_clean_and_tracks_changes(self):
        test_model = create_partial_date_test_model()
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(test_model)

        try:
            instance = test_model(
                date_precision=DatePrecision.YEAR,
                date_qualifier=DateQualifier.NONE,
                start_year=1900,
                sort_date=date(2000, 1, 1),
                sort_date_end=date(2000, 12, 31),
            )
            with patch.object(
                instance,
                "full_clean",
                side_effect=AssertionError("full_clean() must not be called"),
            ):
                instance.save()

            instance.refresh_from_db()
            self.assertEqual(instance.sort_date, date(1900, 1, 1))
            self.assertEqual(instance.sort_date_end, date(1900, 12, 31))

            instance.date_precision = DatePrecision.MONTH
            instance.start_year = 2000
            instance.start_month = 2
            with patch.object(
                instance,
                "full_clean",
                side_effect=AssertionError("full_clean() must not be called"),
            ):
                instance.save(
                    update_fields={
                        "date_precision",
                        "start_year",
                        "start_month",
                    }
                )

            instance.refresh_from_db()
            self.assertEqual(instance.sort_date, date(2000, 2, 1))
            self.assertEqual(instance.sort_date_end, date(2000, 2, 29))
        finally:
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(test_model)

    @isolate_apps("common")
    def test_save_with_empty_update_fields_does_not_write(self):
        test_model = create_partial_date_test_model()
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(test_model)

        try:
            instance = test_model.objects.create(
                date_precision=DatePrecision.YEAR,
                date_qualifier=DateQualifier.NONE,
                start_year=1900,
            )
            instance.start_year = 2000

            with self.assertNumQueries(0):
                instance.save(update_fields=set())

            instance.refresh_from_db()
            self.assertEqual(instance.start_year, 1900)
            self.assertEqual(instance.sort_date, date(1900, 1, 1))
            self.assertEqual(instance.sort_date_end, date(1900, 12, 31))
        finally:
            with connection.schema_editor() as schema_editor:
                schema_editor.delete_model(test_model)
