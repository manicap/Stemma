from datetime import date

from django.contrib import admin
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision, DateQualifier
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)

from .models import Person, Relationship, RelationshipType


class RelationshipModelTests(SimpleTestCase):
    """Ověření struktury a metadat konkrétní vazby."""

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

    def test_model_is_concrete_and_uses_exact_mixins(self) -> None:
        self.assertFalse(Relationship._meta.abstract)
        self.assertEqual(
            Relationship.__bases__,
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

    def test_model_has_exact_own_fields(self) -> None:
        own_fields = tuple(
            field.name
            for field in Relationship._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            own_fields,
            ("relationship_type", "person_a", "person_b", "note"),
        )

    def assert_foreign_key(
        self,
        field_name: str,
        model: type[models.Model],
        related_name: str,
    ) -> None:
        field = Relationship._meta.get_field(field_name)

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, model)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(field.remote_field.related_name, related_name)

    def test_relationship_type_foreign_key(self) -> None:
        self.assert_foreign_key(
            "relationship_type",
            RelationshipType,
            "relationships",
        )

    def test_person_a_foreign_key(self) -> None:
        self.assert_foreign_key(
            "person_a",
            Person,
            "relationships_as_a",
        )

    def test_person_b_foreign_key(self) -> None:
        self.assert_foreign_key(
            "person_b",
            Person,
            "relationships_as_b",
        )

    def test_note_field(self) -> None:
        field = Relationship._meta.get_field("note")

        self.assertIsInstance(field, models.TextField)
        self.assertTrue(field.blank)
        self.assertFalse(field.null)

    def test_constraint_names_and_structure(self) -> None:
        constraints = {
            constraint.name: constraint
            for constraint in Relationship._meta.constraints
        }

        self.assertEqual(
            set(constraints),
            {
                "people_relationship_distinct_persons",
                "people_unique_active_unknown_relationship",
                "people_unique_active_dated_relationship",
            },
        )

        distinct = constraints["people_relationship_distinct_persons"]
        self.assertIsInstance(distinct, models.CheckConstraint)
        self.assertEqual(
            distinct.condition,
            ~models.Q(person_a=models.F("person_b")),
        )

        unknown = constraints[
            "people_unique_active_unknown_relationship"
        ]
        self.assertIsInstance(unknown, models.UniqueConstraint)
        self.assertEqual(
            unknown.fields,
            ("person_a", "person_b", "relationship_type"),
        )
        self.assertEqual(
            unknown.condition,
            models.Q(
                deleted_at__isnull=True,
                date_precision=DatePrecision.UNKNOWN,
            ),
        )
        self.assertEqual(
            unknown.violation_error_code,
            "duplicate_relationship",
        )

        dated = constraints["people_unique_active_dated_relationship"]
        self.assertIsInstance(dated, models.UniqueConstraint)
        self.assertEqual(
            dated.fields,
            (
                "person_a",
                "person_b",
                "relationship_type",
                "date_precision",
                "sort_date",
                "sort_date_end",
            ),
        )
        self.assertEqual(
            dated.condition,
            (
                models.Q(deleted_at__isnull=True)
                & ~models.Q(date_precision=DatePrecision.UNKNOWN)
            ),
        )
        self.assertEqual(
            dated.violation_error_code,
            "duplicate_relationship",
        )

    def test_model_metadata(self) -> None:
        self.assertEqual(Relationship._meta.verbose_name, "Vazba")
        self.assertEqual(
            Relationship._meta.verbose_name_plural,
            "Vazby",
        )
        self.assertEqual(
            Relationship._meta.ordering,
            (
                "relationship_type__sort_order",
                "sort_date",
                "sort_date_end",
                "person_a_id",
                "person_b_id",
                "pk",
            ),
        )

    def test_string_representation(self) -> None:
        person_a = Person(first_name="Jan", last_name="Novák")
        person_b = Person(first_name="Petr", last_name="Novák")
        relationship_type = RelationshipType(name="Biologický rodič")
        relationship = Relationship(
            person_a=person_a,
            person_b=person_b,
            relationship_type=relationship_type,
        )

        self.assertEqual(
            str(relationship),
            "Novák Jan – Biologický rodič – Novák Petr",
        )

    def test_string_representation_fallbacks(self) -> None:
        person_a = Person(first_name="Jan")
        person_b = Person(first_name="Petr")
        relationship_type = RelationshipType(name="Partnerství")

        self.assertEqual(
            str(
                Relationship(
                    relationship_type=relationship_type,
                    person_b=person_b,
                )
            ),
            "Neznámá osoba A – Partnerství – Petr",
        )
        self.assertEqual(
            str(Relationship(person_a=person_a, person_b=person_b)),
            "Jan – Vazba – Petr",
        )
        self.assertEqual(
            str(
                Relationship(
                    relationship_type=relationship_type,
                    person_a=person_a,
                )
            ),
            "Jan – Partnerství – Neznámá osoba B",
        )
        self.assertEqual(
            str(Relationship()),
            "Neznámá osoba A – Vazba – Neznámá osoba B",
        )

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(Relationship))


class RelationshipDatabaseTests(TestCase):
    """Ověření časové validace a databázové integrity vazeb."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.person_a = Person.objects.create(first_name="Anna")
        cls.person_b = Person.objects.create(first_name="Bohumil")
        cls.person_c = Person.objects.create(first_name="Cyril")
        cls.biological_parent = RelationshipType.objects.get(
            code="biological_parent"
        )
        cls.guardian = RelationshipType.objects.get(code="guardian")
        cls.spouse = RelationshipType.objects.get(code="spouse")
        cls.partner = RelationshipType.objects.get(code="partner")
        cls.sibling = RelationshipType.objects.get(code="sibling")

    def relationship(self, **changes) -> Relationship:
        values = {
            "relationship_type": self.biological_parent,
            "person_a": self.person_a,
            "person_b": self.person_b,
        }
        values.update(changes)
        return Relationship(**values)

    def assert_database_rejects(self, relationship: Relationship) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                relationship.save()

    def test_unknown_date_is_valid(self) -> None:
        relationship = self.relationship()

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.date_precision, DatePrecision.UNKNOWN)
        self.assertIsNone(relationship.sort_date)
        self.assertIsNone(relationship.sort_date_end)

    def test_exact_date_derives_sort_bounds(self) -> None:
        relationship = self.relationship(
            date_precision=DatePrecision.EXACT,
            start_year=1990,
            start_month=5,
            start_day=12,
        )

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.sort_date, date(1990, 5, 12))
        self.assertEqual(relationship.sort_date_end, date(1990, 5, 12))

    def test_month_derives_first_and_last_day(self) -> None:
        relationship = self.relationship(
            date_precision=DatePrecision.MONTH,
            start_year=2000,
            start_month=2,
        )

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.sort_date, date(2000, 2, 1))
        self.assertEqual(relationship.sort_date_end, date(2000, 2, 29))

    def test_year_derives_first_and_last_day(self) -> None:
        relationship = self.relationship(
            date_precision=DatePrecision.YEAR,
            start_year=1985,
        )

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.sort_date, date(1985, 1, 1))
        self.assertEqual(relationship.sort_date_end, date(1985, 12, 31))

    def test_supported_range_derives_sort_bounds(self) -> None:
        relationship = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.RANGE,
            start_year=1990,
            start_month=5,
            start_day=12,
            end_year=2000,
            end_month=6,
            end_day=20,
        )

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.sort_date, date(1990, 5, 12))
        self.assertEqual(relationship.sort_date_end, date(2000, 6, 20))

    def test_unsupported_range_is_rejected(self) -> None:
        relationship = self.relationship(
            date_precision=DatePrecision.RANGE,
            start_year=1990,
            end_year=2000,
        )

        with self.assertRaises(ValidationError) as context:
            relationship.full_clean()

        self.assertEqual(
            context.exception.error_dict["date_precision"][0].code,
            "date_range_not_supported",
        )

    def test_qualifier_does_not_change_sort_bounds(self) -> None:
        relationship = self.relationship(
            date_precision=DatePrecision.YEAR,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1985,
        )

        relationship.full_clean()

        self.assertEqual(relationship.sort_date, date(1985, 1, 1))
        self.assertEqual(relationship.sort_date_end, date(1985, 12, 31))

    def test_partial_date_and_relationship_errors_are_aggregated(self) -> None:
        relationship = self.relationship(
            person_b=self.person_a,
            date_precision=DatePrecision.EXACT,
        )

        with self.assertRaises(ValidationError) as context:
            relationship.full_clean()

        self.assertIn("start_year", context.exception.error_dict)
        self.assertIn("person_b", context.exception.error_dict)
        self.assertEqual(
            context.exception.error_dict["person_b"][0].code,
            "relationship_to_self",
        )

    def test_relationship_to_self_is_rejected_by_model(self) -> None:
        relationship = self.relationship(person_b=self.person_a)

        with self.assertRaises(ValidationError) as context:
            relationship.full_clean()

        self.assertEqual(
            context.exception.error_dict["person_b"][0].code,
            "relationship_to_self",
        )

    def test_relationship_to_self_is_rejected_by_database(self) -> None:
        self.assert_database_rejects(
            self.relationship(person_b=self.person_a)
        )

    def test_normalized_symmetric_relationship_is_valid(self) -> None:
        relationship = self.relationship(
            relationship_type=self.sibling,
        )

        relationship.full_clean()
        relationship.save()

        self.assertEqual(relationship.person_a_id, self.person_a.pk)
        self.assertEqual(relationship.person_b_id, self.person_b.pk)

    def test_reversed_symmetric_relationship_is_rejected_without_swap(
        self,
    ) -> None:
        relationship = self.relationship(
            relationship_type=self.sibling,
            person_a=self.person_b,
            person_b=self.person_a,
        )

        with self.assertRaises(ValidationError) as context:
            relationship.full_clean()

        self.assertEqual(
            context.exception.error_dict["person_b"][0].code,
            "symmetric_relationship_not_normalized",
        )
        self.assertEqual(relationship.person_a_id, self.person_b.pk)
        self.assertEqual(relationship.person_b_id, self.person_a.pk)

    def test_asymmetric_relationship_allows_both_orientations(self) -> None:
        forward = self.relationship()
        reverse = self.relationship(
            person_a=self.person_b,
            person_b=self.person_a,
        )

        forward.full_clean()
        forward.save()
        reverse.full_clean()
        reverse.save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_incomplete_instances_do_not_raise_related_object_error(
        self,
    ) -> None:
        Relationship().clean()
        Relationship(
            relationship_type=RelationshipType(
                is_symmetric=True,
            ),
            person_a=Person(first_name="Neuložená A"),
            person_b=Person(first_name="Neuložená B"),
        ).clean()

    def test_foreign_keys_are_protected(self) -> None:
        relationship = self.relationship()
        relationship.save()

        for protected_object in (
            self.person_a,
            self.person_b,
            self.biological_parent,
        ):
            with self.subTest(protected_object=protected_object):
                with self.assertRaises(ProtectedError):
                    protected_object.delete()

    def test_unknown_duplicate_is_rejected_by_database(self) -> None:
        self.relationship().save()

        self.assert_database_rejects(self.relationship())

    def test_unknown_duplicate_has_stable_model_validation_code(self) -> None:
        self.relationship().save()
        duplicate = self.relationship()

        with self.assertRaises(ValidationError) as context:
            duplicate.full_clean()

        self.assertEqual(
            context.exception.error_dict[NON_FIELD_ERRORS][0].code,
            "duplicate_relationship",
        )

    def test_note_and_access_level_do_not_distinguish_unknown_period(
        self,
    ) -> None:
        self.relationship(note="První poznámka").save()

        self.assert_database_rejects(
            self.relationship(
                note="Jiná poznámka",
                access_level=AccessLevel.RESTRICTED,
            )
        )

    def test_archived_unknown_relationship_still_blocks_duplicate(
        self,
    ) -> None:
        relationship = self.relationship()
        relationship.save()
        relationship.archived_at = timezone.now()
        relationship.save(update_fields={"archived_at"})

        self.assert_database_rejects(self.relationship())

    def test_soft_deleted_unknown_relationship_allows_replacement(
        self,
    ) -> None:
        relationship = self.relationship()
        relationship.save()
        relationship.deleted_at = timezone.now()
        relationship.save(update_fields={"deleted_at"})

        replacement = self.relationship()
        replacement.save()

        self.assertNotEqual(relationship.pk, replacement.pk)

    def test_restoring_unknown_relationship_can_conflict(self) -> None:
        relationship = self.relationship()
        relationship.save()
        relationship.deleted_at = timezone.now()
        relationship.save(update_fields={"deleted_at"})
        self.relationship().save()

        relationship.deleted_at = None
        self.assert_database_rejects(relationship)

    def assert_dated_duplicate_is_rejected(self, **date_values) -> None:
        first = self.relationship(
            relationship_type=self.spouse,
            **date_values,
        )
        duplicate = self.relationship(
            relationship_type=self.spouse,
            **date_values,
        )
        first.save()

        self.assert_database_rejects(duplicate)

    def test_exact_duplicate_is_rejected(self) -> None:
        self.assert_dated_duplicate_is_rejected(
            date_precision=DatePrecision.EXACT,
            start_year=1990,
            start_month=5,
            start_day=12,
        )

    def test_month_duplicate_is_rejected(self) -> None:
        self.assert_dated_duplicate_is_rejected(
            date_precision=DatePrecision.MONTH,
            start_year=1990,
            start_month=5,
        )

    def test_year_duplicate_is_rejected(self) -> None:
        self.assert_dated_duplicate_is_rejected(
            date_precision=DatePrecision.YEAR,
            start_year=1990,
        )

    def test_range_duplicate_is_rejected(self) -> None:
        self.assert_dated_duplicate_is_rejected(
            date_precision=DatePrecision.RANGE,
            start_year=1990,
            end_year=2000,
        )

    def test_dated_duplicate_has_stable_model_validation_code(self) -> None:
        values = {
            "relationship_type": self.spouse,
            "date_precision": DatePrecision.YEAR,
            "start_year": 1990,
        }
        existing = self.relationship(**values)
        existing.save()
        duplicate = self.relationship(**values)

        with self.assertRaises(ValidationError) as context:
            duplicate.full_clean()

        self.assertEqual(
            context.exception.error_dict[NON_FIELD_ERRORS][0].code,
            "duplicate_relationship",
        )

    def test_different_known_starts_are_allowed(self) -> None:
        first = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.YEAR,
            start_year=1990,
        )
        second = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.YEAR,
            start_year=2000,
        )

        first.save()
        second.save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_different_ranges_are_allowed(self) -> None:
        first = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.RANGE,
            start_year=1990,
            end_year=2000,
        )
        second = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.RANGE,
            start_year=2005,
            end_year=2010,
        )

        first.save()
        second.save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_different_precisions_are_distinct_identities(self) -> None:
        year = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.YEAR,
            start_year=1990,
        )
        range_relationship = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.RANGE,
            start_year=1990,
            start_month=1,
            start_day=1,
            end_year=1990,
            end_month=12,
            end_day=31,
        )

        year.save()
        range_relationship.save()

        self.assertEqual(year.sort_date, range_relationship.sort_date)
        self.assertEqual(
            year.sort_date_end,
            range_relationship.sort_date_end,
        )
        self.assertEqual(Relationship.objects.count(), 2)

    def test_soft_deleted_dated_relationship_allows_replacement(self) -> None:
        relationship = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.YEAR,
            start_year=1990,
        )
        relationship.save()
        relationship.deleted_at = timezone.now()
        relationship.save(update_fields={"deleted_at"})

        replacement = self.relationship(
            relationship_type=self.spouse,
            date_precision=DatePrecision.YEAR,
            start_year=1990,
        )
        replacement.save()

        self.assertNotEqual(relationship.pk, replacement.pk)

    def test_repeated_marriages_are_allowed(self) -> None:
        for start_year, end_year in ((1990, 1995), (2000, 2005)):
            self.relationship(
                relationship_type=self.spouse,
                date_precision=DatePrecision.RANGE,
                start_year=start_year,
                end_year=end_year,
            ).save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_repeated_partnerships_are_allowed(self) -> None:
        for start_year in (1990, 2000):
            self.relationship(
                relationship_type=self.partner,
                date_precision=DatePrecision.YEAR,
                start_year=start_year,
            ).save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_overlapping_nonidentical_periods_are_allowed(self) -> None:
        for start_year, end_year in ((1990, 2000), (1995, 2005)):
            self.relationship(
                relationship_type=self.partner,
                date_precision=DatePrecision.RANGE,
                start_year=start_year,
                end_year=end_year,
            ).save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_same_people_can_have_different_relationship_types(self) -> None:
        self.relationship().save()
        self.relationship(relationship_type=self.guardian).save()

        self.assertEqual(Relationship.objects.count(), 2)

    def test_person_can_participate_many_times_as_a_and_b(self) -> None:
        self.relationship().save()
        self.relationship(
            relationship_type=self.guardian,
            person_b=self.person_c,
        ).save()
        self.relationship(
            relationship_type=self.biological_parent,
            person_a=self.person_c,
            person_b=self.person_a,
        ).save()

        self.assertEqual(self.person_a.relationships_as_a.count(), 2)
        self.assertEqual(self.person_a.relationships_as_b.count(), 1)

    def test_explicit_derivable_sibling_is_allowed_without_side_effects(
        self,
    ) -> None:
        relationship = self.relationship(relationship_type=self.sibling)

        relationship.full_clean()
        relationship.save()

        self.assertTrue(relationship.relationship_type.is_derivable)
        self.assertEqual(Relationship.objects.count(), 1)
