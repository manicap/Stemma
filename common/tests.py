from django.apps import apps
from django.conf import settings
from django.db import models
from django.test import SimpleTestCase

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
    TimestampedModel,
    VerifiableModel,
)


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

    def test_abstract_models_are_not_registered_as_concrete_models(self):
        registered_models = set(apps.get_models())

        for abstract_model in self.abstract_models:
            with self.subTest(model=abstract_model.__name__):
                self.assertNotIn(abstract_model, registered_models)