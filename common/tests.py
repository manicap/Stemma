from django.test import SimpleTestCase

from .choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    Gender,
    VerificationStatus,
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
