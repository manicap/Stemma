from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.models import LookupModel

from .choices import RelationshipCategory
from .models import RelationshipType


RELATIONSHIP_CATEGORY_CHOICES = (
    ("parent_child", "Rodič a dítě"),
    ("partner", "Partnerství"),
    ("sibling", "Sourozenectví"),
    ("godparent", "Kmotrovství"),
    ("care", "Péče a poručenství"),
    ("social", "Sociální vazba"),
    ("other", "Jiná vazba"),
)
RELATIONSHIP_TYPE_FIELDS = (
    "code",
    "name",
    "description",
    "category",
    "sort_order",
    "forward_label_male",
    "forward_label_female",
    "forward_label_unknown",
    "reverse_label_male",
    "reverse_label_female",
    "reverse_label_unknown",
    "is_symmetric",
    "supports_date_range",
    "is_derivable",
    "is_active",
    "is_system",
)
INITIAL_RELATIONSHIP_TYPES = (
    (
        "biological_parent",
        "Biologický rodič",
        "Vztah biologického rodiče a dítěte.",
        "parent_child",
        10,
        "syn",
        "dcera",
        "dítě",
        "otec",
        "matka",
        "rodič",
        False,
        False,
        False,
        True,
        True,
    ),
    (
        "adoptive_parent",
        "Adoptivní rodič",
        "Vztah adoptivního rodiče a adoptovaného dítěte.",
        "parent_child",
        20,
        "adoptovaný syn",
        "adoptovaná dcera",
        "adoptované dítě",
        "adoptivní otec",
        "adoptivní matka",
        "adoptivní rodič",
        False,
        False,
        False,
        True,
        True,
    ),
    (
        "step_parent",
        "Nevlastní rodič",
        "Vztah nevlastního rodiče a nevlastního dítěte.",
        "parent_child",
        30,
        "nevlastní syn",
        "nevlastní dcera",
        "nevlastní dítě",
        "nevlastní otec",
        "nevlastní matka",
        "nevlastní rodič",
        False,
        True,
        False,
        True,
        True,
    ),
    (
        "foster_parent",
        "Pěstoun",
        "Vztah pěstouna a dítěte v pěstounské péči.",
        "parent_child",
        40,
        "pěstounský syn",
        "pěstounská dcera",
        "dítě v pěstounské péči",
        "pěstoun",
        "pěstounka",
        "pěstoun nebo pěstounka",
        False,
        True,
        False,
        True,
        True,
    ),
    (
        "guardian",
        "Poručník",
        "Vztah poručníka a osoby v poručenství.",
        "care",
        50,
        "svěřenec",
        "svěřenkyně",
        "osoba v poručenství",
        "poručník",
        "poručnice",
        "poručník nebo poručnice",
        False,
        True,
        False,
        True,
        True,
    ),
    (
        "spouse",
        "Manželství",
        "Manželský vztah mezi dvěma osobami.",
        "partner",
        60,
        "manžel",
        "manželka",
        "manžel nebo manželka",
        "manžel",
        "manželka",
        "manžel nebo manželka",
        True,
        True,
        False,
        True,
        True,
    ),
    (
        "partner",
        "Partnerství",
        "Partnerský vztah mezi dvěma osobami.",
        "partner",
        70,
        "partner",
        "partnerka",
        "partner nebo partnerka",
        "partner",
        "partnerka",
        "partner nebo partnerka",
        True,
        True,
        False,
        True,
        True,
    ),
    (
        "sibling",
        "Biologické sourozenectví",
        "Biologické sourozenectví.",
        "sibling",
        80,
        "bratr",
        "sestra",
        "sourozenec",
        "bratr",
        "sestra",
        "sourozenec",
        True,
        False,
        True,
        True,
        True,
    ),
    (
        "adoptive_sibling",
        "Adoptivní sourozenectví",
        "Sourozenectví vzniklé adopcí.",
        "sibling",
        90,
        "adoptivní bratr",
        "adoptivní sestra",
        "adoptivní sourozenec",
        "adoptivní bratr",
        "adoptivní sestra",
        "adoptivní sourozenec",
        True,
        False,
        False,
        True,
        True,
    ),
    (
        "step_sibling",
        "Nevlastní sourozenectví",
        "Nevlastní sourozenectví.",
        "sibling",
        100,
        "nevlastní bratr",
        "nevlastní sestra",
        "nevlastní sourozenec",
        "nevlastní bratr",
        "nevlastní sestra",
        "nevlastní sourozenec",
        True,
        True,
        False,
        True,
        True,
    ),
    (
        "social_sibling",
        "Sourozenecká sociální vazba",
        (
            "Sourozenecká sociální vazba bez biologického nebo právního "
            "základu."
        ),
        "sibling",
        110,
        "blízký jako bratr",
        "blízká jako sestra",
        "blízký jako sourozenec",
        "blízký jako bratr",
        "blízká jako sestra",
        "blízký jako sourozenec",
        True,
        True,
        False,
        True,
        True,
    ),
    (
        "godparent",
        "Kmotrovství",
        "Vztah kmotra nebo kmotry a kmotřence.",
        "godparent",
        120,
        "kmotřenec",
        "kmotřenka",
        "kmotřenec nebo kmotřenka",
        "kmotr",
        "kmotra",
        "kmotr nebo kmotra",
        False,
        False,
        False,
        True,
        True,
    ),
    (
        "family_friend",
        "Rodinné přátelství",
        "Blízká přátelská vazba osoby k rodině.",
        "social",
        130,
        "rodinný přítel",
        "rodinná přítelkyně",
        "rodinný přítel nebo přítelkyně",
        "rodinný přítel",
        "rodinná přítelkyně",
        "rodinný přítel nebo přítelkyně",
        True,
        True,
        False,
        True,
        True,
    ),
    (
        "other",
        "Jiná vazba",
        "Jiná rodinná nebo sociální vazba.",
        "other",
        140,
        "související osoba",
        "související osoba",
        "související osoba",
        "související osoba",
        "související osoba",
        "související osoba",
        True,
        True,
        False,
        True,
        True,
    ),
)
INITIAL_RELATIONSHIP_TYPE_CODES = tuple(
    relationship_type[0]
    for relationship_type in INITIAL_RELATIONSHIP_TYPES
)


class RelationshipCategoryTests(SimpleTestCase):
    """Ověření pevného výčtu kategorií vztahů."""

    def test_values_labels_and_order_are_exact(self) -> None:
        self.assertEqual(
            tuple(RelationshipCategory.choices),
            RELATIONSHIP_CATEGORY_CHOICES,
        )

    def test_values_are_unique(self) -> None:
        values = tuple(RelationshipCategory.values)

        self.assertEqual(len(values), len(set(values)))


class RelationshipTypeModelTests(SimpleTestCase):
    """Ověření struktury a metadat číselníku typů vazeb."""

    lookup_field_names = {
        "id",
        "code",
        "name",
        "description",
        "sort_order",
        "is_active",
        "is_system",
    }

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(RelationshipType._meta.abstract)
        self.assertEqual(RelationshipType.__bases__, (LookupModel,))

    def test_model_has_exact_own_fields_in_order(self) -> None:
        own_fields = tuple(
            field.name
            for field in RelationshipType._meta.local_fields
            if field.name not in self.lookup_field_names
        )

        self.assertEqual(
            own_fields,
            (
                "forward_label_male",
                "forward_label_female",
                "forward_label_unknown",
                "reverse_label_male",
                "reverse_label_female",
                "reverse_label_unknown",
                "category",
                "is_symmetric",
                "supports_date_range",
                "is_derivable",
            ),
        )

    def test_label_fields_have_exact_parameters(self) -> None:
        for field_name in (
            "forward_label_male",
            "forward_label_female",
            "forward_label_unknown",
            "reverse_label_male",
            "reverse_label_female",
            "reverse_label_unknown",
        ):
            with self.subTest(field_name=field_name):
                field = RelationshipType._meta.get_field(field_name)
                self.assertIsInstance(field, models.CharField)
                self.assertEqual(field.max_length, 100)
                self.assertFalse(field.blank)
                self.assertFalse(field.null)

    def test_category_field_has_exact_parameters(self) -> None:
        field = RelationshipType._meta.get_field("category")

        self.assertIsInstance(field, models.CharField)
        self.assertEqual(field.max_length, 20)
        self.assertEqual(field.choices, RelationshipCategory.choices)
        self.assertEqual(field.default, RelationshipCategory.OTHER)

    def test_boolean_fields_default_to_false(self) -> None:
        for field_name in (
            "is_symmetric",
            "supports_date_range",
            "is_derivable",
        ):
            with self.subTest(field_name=field_name):
                field = RelationshipType._meta.get_field(field_name)
                self.assertIsInstance(field, models.BooleanField)
                self.assertFalse(field.default)

    def test_model_metadata_and_string_representation(self) -> None:
        relationship_type = RelationshipType(
            code="test",
            name="Testovací vazba",
        )

        self.assertEqual(
            RelationshipType._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(
            RelationshipType._meta.verbose_name,
            "Typ vazby",
        )
        self.assertEqual(
            RelationshipType._meta.verbose_name_plural,
            "Typy vazeb",
        )
        self.assertEqual(str(relationship_type), "Testovací vazba")

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(RelationshipType))


class RelationshipTypeValidationTests(TestCase):
    """Ověření modelové a databázové validace symetrických názvů."""

    @staticmethod
    def relationship_type(**changes) -> RelationshipType:
        values = {
            "code": "test",
            "name": "Testovací vazba",
            "forward_label_male": "bratr",
            "forward_label_female": "sestra",
            "forward_label_unknown": "sourozenec",
            "reverse_label_male": "bratr",
            "reverse_label_female": "sestra",
            "reverse_label_unknown": "sourozenec",
            "is_symmetric": True,
        }
        values.update(changes)
        return RelationshipType(**values)

    def test_matching_symmetric_labels_pass_full_clean(self) -> None:
        self.relationship_type().full_clean()

    def assert_symmetric_mismatch_rejected(
        self,
        field_name: str,
        value: str,
    ) -> None:
        relationship_type = self.relationship_type(**{field_name: value})

        with self.assertRaises(ValidationError) as context:
            relationship_type.full_clean()

        self.assertEqual(
            context.exception.error_dict[field_name][0].code,
            "symmetric_labels_mismatch",
        )

    def test_male_symmetric_label_mismatch_is_rejected(self) -> None:
        self.assert_symmetric_mismatch_rejected(
            "reverse_label_male",
            "jiný bratr",
        )

    def test_female_symmetric_label_mismatch_is_rejected(self) -> None:
        self.assert_symmetric_mismatch_rejected(
            "reverse_label_female",
            "jiná sestra",
        )

    def test_unknown_symmetric_label_mismatch_is_rejected(self) -> None:
        self.assert_symmetric_mismatch_rejected(
            "reverse_label_unknown",
            "jiný sourozenec",
        )

    def test_asymmetric_type_can_use_different_labels(self) -> None:
        relationship_type = self.relationship_type(
            is_symmetric=False,
            reverse_label_male="otec",
            reverse_label_female="matka",
            reverse_label_unknown="rodič",
        )

        relationship_type.full_clean()

    def test_database_constraint_rejects_invalid_symmetric_type(self) -> None:
        relationship_type = self.relationship_type(
            reverse_label_unknown="jiný sourozenec"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                relationship_type.save()


class RelationshipTypeDataMigrationTests(TestCase):
    """Ověření systémových typů a vratnosti datové migrace."""

    migration = import_module(
        "people.migrations.0007_initial_relationship_types"
    )

    def test_initial_relationship_types_have_exact_values(self) -> None:
        relationship_types = list(
            RelationshipType.objects.order_by("sort_order").values_list(
                *RELATIONSHIP_TYPE_FIELDS
            )
        )

        self.assertEqual(
            relationship_types,
            list(INITIAL_RELATIONSHIP_TYPES),
        )
        self.assertEqual(len(relationship_types), 14)
        self.assertEqual(
            len(INITIAL_RELATIONSHIP_TYPE_CODES),
            len(set(INITIAL_RELATIONSHIP_TYPE_CODES)),
        )

    def test_only_biological_sibling_is_derivable(self) -> None:
        self.assertEqual(
            list(
                RelationshipType.objects.filter(
                    is_derivable=True
                ).values_list("code", flat=True)
            ),
            ["sibling"],
        )

    def test_forward_migration_is_idempotent(self) -> None:
        RelationshipType.objects.filter(code="biological_parent").update(
            name="Dočasně změněný název",
            is_active=False,
            is_system=False,
        )

        self.migration.create_initial_relationship_types(apps, None)
        self.migration.create_initial_relationship_types(apps, None)

        relationship_type = RelationshipType.objects.get(
            code="biological_parent"
        )
        self.assertEqual(RelationshipType.objects.count(), 14)
        self.assertEqual(relationship_type.name, "Biologický rodič")
        self.assertTrue(relationship_type.is_active)
        self.assertTrue(relationship_type.is_system)

    def test_reverse_migration_removes_only_matching_system_types(self) -> None:
        RelationshipType.objects.filter(code="other").update(
            name="Uživatelská hodnota",
            is_system=False,
        )
        custom_type = RelationshipType.objects.create(
            code="custom",
            name="Vlastní typ",
            forward_label_male="známý",
            forward_label_female="známá",
            forward_label_unknown="známá osoba",
            reverse_label_male="známý",
            reverse_label_female="známá",
            reverse_label_unknown="známá osoba",
            is_symmetric=True,
        )

        self.migration.remove_initial_relationship_types(apps, None)

        self.assertFalse(
            RelationshipType.objects.filter(
                code__in=(
                    code
                    for code in INITIAL_RELATIONSHIP_TYPE_CODES
                    if code != "other"
                )
            ).exists()
        )
        self.assertTrue(
            RelationshipType.objects.filter(code="other").exists()
        )
        self.assertTrue(
            RelationshipType.objects.filter(pk=custom_type.pk).exists()
        )
