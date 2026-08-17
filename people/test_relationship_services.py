from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, timedelta
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)

from . import services
from .models import Person, Relationship, RelationshipType
from .services import (
    RelationshipInput,
    create_relationship,
    update_relationship,
)


class RelationshipServiceApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu služby vazeb."""

    def test_module_exports_only_approved_public_api(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "PersonInput",
                "RelationshipInput",
                "create_person",
                "create_relationship",
                "update_relationship",
            ),
        )

    def test_input_is_frozen_slotted_dataclass(self) -> None:
        data = RelationshipInput(
            relationship_type=RelationshipType(),
            person_a=Person(),
            person_b=Person(),
        )

        self.assertFalse(hasattr(data, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            data.note = "Změna"

    def test_input_has_exact_fields_in_order(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(RelationshipInput)),
            (
                "relationship_type",
                "person_a",
                "person_b",
                "note",
                "access_level",
                "verification_status",
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
            ),
        )

    def test_input_defaults_match_contract(self) -> None:
        data = RelationshipInput(
            relationship_type=RelationshipType(),
            person_a=Person(),
            person_b=Person(),
        )

        self.assertEqual(data.note, "")
        self.assertEqual(data.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            data.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(data.date_precision, DatePrecision.UNKNOWN)
        self.assertEqual(data.date_qualifier, DateQualifier.NONE)
        self.assertIsNone(data.start_year)
        self.assertIsNone(data.start_month)
        self.assertIsNone(data.start_day)
        self.assertIsNone(data.end_year)
        self.assertIsNone(data.end_month)
        self.assertIsNone(data.end_day)
        self.assertEqual(data.original_date_text, "")
        self.assertEqual(data.date_note, "")

    def test_create_contract_is_keyword_only(self) -> None:
        parameters = signature(create_relationship).parameters

        self.assertEqual(tuple(parameters), ("data", "created_by"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )

    def test_update_contract_is_keyword_only(self) -> None:
        parameters = signature(update_relationship).parameters

        self.assertEqual(tuple(parameters), ("relationship", "data"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class RelationshipServiceTests(TestCase):
    """Integrační testy vytvoření a změny jednotlivé vazby."""

    def setUp(self) -> None:
        self.person_a = Person.objects.create(
            first_name="Anna",
            last_name="První",
        )
        self.person_b = Person.objects.create(
            first_name="Bohumil",
            last_name="Druhý",
        )
        self.person_c = Person.objects.create(
            first_name="Cyril",
            last_name="Třetí",
        )
        self.directional_type = self.make_type(
            "service_directional",
            name="Směrová vazba",
        )
        self.symmetric_type = self.make_type(
            "service_symmetric",
            name="Symetrická vazba",
            symmetric=True,
            supports_date_range=True,
        )

    @staticmethod
    def make_type(
        code: str,
        *,
        name: str | None = None,
        symmetric: bool = False,
        supports_date_range: bool = False,
        is_active: bool = True,
        is_derivable: bool = False,
    ) -> RelationshipType:
        forward = "blízká osoba" if symmetric else "potomek"
        reverse = forward if symmetric else "předek"
        return RelationshipType.objects.create(
            code=code,
            name=name or code,
            forward_label_male=forward,
            forward_label_female=forward,
            forward_label_unknown=forward,
            reverse_label_male=reverse,
            reverse_label_female=reverse,
            reverse_label_unknown=reverse,
            is_symmetric=symmetric,
            supports_date_range=supports_date_range,
            is_active=is_active,
            is_derivable=is_derivable,
        )

    def make_data(self, **changes: object) -> RelationshipInput:
        data = RelationshipInput(
            relationship_type=self.directional_type,
            person_a=self.person_a,
            person_b=self.person_b,
        )
        return replace(data, **changes)

    def create_base_relationship(self, **changes: object) -> Relationship:
        return create_relationship(data=self.make_data(**changes))

    def assert_error(
        self,
        context,
        *,
        key: str,
        code: str,
    ) -> ValidationError:
        self.assertIn(key, context.exception.error_dict)
        errors = context.exception.error_dict[key]
        self.assertIn(code, [error.code for error in errors])
        return next(error for error in errors if error.code == code)

    def test_create_valid_directional_relationship(self) -> None:
        result = create_relationship(data=self.make_data())

        self.assertIsInstance(result, Relationship)
        self.assertEqual(result.relationship_type_id, self.directional_type.pk)
        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)
        self.assertEqual(Relationship.objects.count(), 1)

    def test_create_valid_symmetric_relationship(self) -> None:
        result = create_relationship(
            data=self.make_data(relationship_type=self.symmetric_type)
        )

        self.assertEqual(result.relationship_type_id, self.symmetric_type.pk)
        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)

    def test_create_normalizes_reversed_symmetric_people(self) -> None:
        data = self.make_data(
            relationship_type=self.symmetric_type,
            person_a=self.person_b,
            person_b=self.person_a,
        )

        result = create_relationship(data=data)

        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)
        self.assertIs(data.person_a, self.person_b)
        self.assertIs(data.person_b, self.person_a)

    def test_create_preserves_directional_orientation(self) -> None:
        result = create_relationship(
            data=self.make_data(
                person_a=self.person_b,
                person_b=self.person_a,
            )
        )

        self.assertEqual(result.person_a_id, self.person_b.pk)
        self.assertEqual(result.person_b_id, self.person_a.pk)

    def test_create_transfers_all_approved_values(self) -> None:
        user = get_user_model().objects.create_user(
            username="relationship-author"
        )
        data = self.make_data(
            relationship_type=self.symmetric_type,
            note="Doložená vazba",
            access_level=AccessLevel.RESTRICTED,
            verification_status=VerificationStatus.VERIFIED,
            date_precision=DatePrecision.RANGE,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1900,
            start_month=2,
            start_day=3,
            end_year=1910,
            end_month=4,
            end_day=5,
            original_date_text="asi 1900–1910",
            date_note="Rozmezí podle pramene",
        )

        result = create_relationship(data=data, created_by=user)

        self.assertEqual(result.note, "Doložená vazba")
        self.assertEqual(result.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.created_by_id, user.pk)
        self.assertEqual(result.date_precision, DatePrecision.RANGE)
        self.assertEqual(
            result.date_qualifier,
            DateQualifier.APPROXIMATE,
        )
        self.assertEqual(result.start_year, 1900)
        self.assertEqual(result.start_month, 2)
        self.assertEqual(result.start_day, 3)
        self.assertEqual(result.end_year, 1910)
        self.assertEqual(result.end_month, 4)
        self.assertEqual(result.end_day, 5)
        self.assertEqual(result.original_date_text, "asi 1900–1910")
        self.assertEqual(result.date_note, "Rozmezí podle pramene")
        self.assertEqual(result.sort_date, date(1900, 2, 3))
        self.assertEqual(result.sort_date_end, date(1910, 4, 5))

    def test_create_returns_fresh_select_related_relationship(self) -> None:
        result = create_relationship(data=self.make_data())

        self.assertFalse(result._state.adding)
        self.assertEqual(
            set(result._state.fields_cache),
            {"relationship_type", "person_a", "person_b", "created_by"},
        )

    def test_update_note_and_keeps_primary_key(self) -> None:
        relationship = self.create_base_relationship(note="Původní")

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(note="Nová"),
        )

        self.assertEqual(result.pk, relationship.pk)
        self.assertEqual(result.note, "Nová")
        self.assertIsNot(result, relationship)

    def test_update_changes_date_and_derived_values(self) -> None:
        relationship = self.create_base_relationship()

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(
                date_precision=DatePrecision.EXACT,
                start_year=1985,
                start_month=6,
                start_day=7,
            ),
        )

        self.assertEqual(result.date_precision, DatePrecision.EXACT)
        self.assertEqual(result.sort_date, date(1985, 6, 7))
        self.assertEqual(result.sort_date_end, date(1985, 6, 7))

    def test_update_changes_access_verification_and_date_texts(self) -> None:
        relationship = self.create_base_relationship()

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.DISPUTED,
                original_date_text="po roce 1900",
                date_note="Nejistý zápis",
            ),
        )

        self.assertEqual(result.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.DISPUTED,
        )
        self.assertEqual(result.original_date_text, "po roce 1900")
        self.assertEqual(result.date_note, "Nejistý zápis")

    def test_update_changes_type_and_people(self) -> None:
        relationship = self.create_base_relationship()
        replacement_type = self.make_type("service_replacement")

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(
                relationship_type=replacement_type,
                person_a=self.person_c,
                person_b=self.person_a,
            ),
        )

        self.assertEqual(result.relationship_type_id, replacement_type.pk)
        self.assertEqual(result.person_a_id, self.person_c.pk)
        self.assertEqual(result.person_b_id, self.person_a.pk)

    def test_update_to_symmetric_type_normalizes_people(self) -> None:
        relationship = self.create_base_relationship()

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(
                relationship_type=self.symmetric_type,
                person_a=self.person_b,
                person_b=self.person_a,
            ),
        )

        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)

    def test_update_to_directional_type_preserves_orientation(self) -> None:
        relationship = create_relationship(
            data=self.make_data(relationship_type=self.symmetric_type)
        )

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(
                person_a=self.person_b,
                person_b=self.person_a,
            ),
        )

        self.assertEqual(result.person_a_id, self.person_b.pk)
        self.assertEqual(result.person_b_id, self.person_a.pk)

    def test_update_preserves_created_by_and_lifecycle_fields(self) -> None:
        creator = get_user_model().objects.create_user(username="creator")
        actor = get_user_model().objects.create_user(username="archivist")
        relationship = create_relationship(
            data=self.make_data(),
            created_by=creator,
        )
        archived_at = timezone.now() - timedelta(days=1)
        Relationship.objects.filter(pk=relationship.pk).update(
            archived_at=archived_at,
            archived_by=actor,
            archive_reason="Historický záznam",
        )

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(note="Doplněno"),
        )

        self.assertEqual(result.created_by_id, creator.pk)
        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archived_by_id, actor.pk)
        self.assertEqual(result.archive_reason, "Historický záznam")
        self.assertIsNone(result.deleted_at)
        self.assertIsNone(result.deleted_by_id)
        self.assertEqual(result.deletion_reason, "")

    def test_update_refreshes_updated_at(self) -> None:
        relationship = self.create_base_relationship()
        changed_at = relationship.updated_at + timedelta(days=1)

        with patch("django.utils.timezone.now", return_value=changed_at):
            result = update_relationship(
                relationship=relationship,
                data=self.make_data(note="Později"),
            )

        self.assertEqual(result.updated_at, changed_at)

    def test_update_uses_select_for_update(self) -> None:
        relationship = self.create_base_relationship()

        with patch.object(
            Relationship.objects,
            "select_for_update",
            wraps=Relationship.objects.select_for_update,
        ) as mocked_lock:
            update_relationship(
                relationship=relationship,
                data=self.make_data(note="Uzamčeno"),
            )

        mocked_lock.assert_called()

    def test_rejects_unsaved_relationship_type(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_relationship(
                data=self.make_data(
                    relationship_type=RelationshipType(name="Nový")
                )
            )

        self.assert_error(
            context,
            key="relationship_type",
            code="relationship_type_unsaved",
        )

    def test_rejects_deleted_relationship_type(self) -> None:
        missing = self.make_type("service_missing_type")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            create_relationship(
                data=self.make_data(relationship_type=missing)
            )

        self.assert_error(
            context,
            key="relationship_type",
            code="relationship_type_unsaved",
        )

    def test_rejects_unsaved_person_a_and_person_b(self) -> None:
        for key, code, changes in (
            (
                "person_a",
                "relationship_person_a_unsaved",
                {"person_a": Person(first_name="Nová A")},
            ),
            (
                "person_b",
                "relationship_person_b_unsaved",
                {"person_b": Person(first_name="Nová B")},
            ),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError) as context:
                    create_relationship(data=self.make_data(**changes))
                self.assert_error(context, key=key, code=code)

    def test_rejects_deleted_person_a_and_person_b(self) -> None:
        for index, (key, code) in enumerate(
            (
            (
                "person_a",
                "relationship_person_a_unsaved",
            ),
            (
                "person_b",
                "relationship_person_b_unsaved",
            ),
            ),
            start=1,
        ):
            with self.subTest(key=key):
                person = Person.objects.create(
                    first_name=f"Odstraněná {index}"
                )
                person_pk = person.pk
                person.delete()
                person.pk = person_pk
                changes = {
                    "person_a": self.person_a,
                    "person_b": self.person_b,
                    key: person,
                }
                with self.assertRaises(ValidationError) as context:
                    create_relationship(data=self.make_data(**changes))
                self.assert_error(context, key=key, code=code)

    def test_rejects_unsaved_created_by(self) -> None:
        user = get_user_model()(username="unsaved-author")

        with self.assertRaises(ValidationError) as context:
            create_relationship(data=self.make_data(), created_by=user)

        self.assert_error(
            context,
            key="created_by",
            code="relationship_created_by_unsaved",
        )

    def test_rejects_deleted_created_by(self) -> None:
        user = get_user_model().objects.create_user(username="deleted-author")
        user_pk = user.pk
        user.delete()
        user.pk = user_pk

        with self.assertRaises(ValidationError) as context:
            create_relationship(data=self.make_data(), created_by=user)

        self.assert_error(
            context,
            key="created_by",
            code="relationship_created_by_unsaved",
        )

    def test_inactive_created_by_is_allowed(self) -> None:
        user = get_user_model().objects.create_user(
            username="inactive-author",
            is_active=False,
        )

        result = create_relationship(
            data=self.make_data(),
            created_by=user,
        )

        self.assertEqual(result.created_by_id, user.pk)

    def test_rejects_unsaved_and_deleted_relationship_on_update(self) -> None:
        with self.assertRaises(ValidationError) as unsaved_context:
            update_relationship(
                relationship=Relationship(),
                data=self.make_data(),
            )
        self.assert_error(
            unsaved_context,
            key="relationship",
            code="relationship_unsaved",
        )

        missing = self.create_base_relationship()
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        with self.assertRaises(ValidationError) as missing_context:
            update_relationship(relationship=missing, data=self.make_data())
        self.assert_error(
            missing_context,
            key="relationship",
            code="relationship_unsaved",
        )

    def test_create_rejects_inactive_type_using_current_state(self) -> None:
        inactive = self.make_type("service_inactive_create")
        RelationshipType.objects.filter(pk=inactive.pk).update(
            is_active=False
        )
        self.assertTrue(inactive.is_active)

        with self.assertRaises(ValidationError) as context:
            create_relationship(
                data=self.make_data(relationship_type=inactive)
            )

        self.assert_error(
            context,
            key="relationship_type",
            code="relationship_type_inactive",
        )

    def test_update_may_keep_same_inactive_type(self) -> None:
        relationship = self.create_base_relationship()
        RelationshipType.objects.filter(pk=self.directional_type.pk).update(
            is_active=False
        )

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(note="Typ zůstává"),
        )

        self.assertEqual(result.relationship_type_id, self.directional_type.pk)
        self.assertEqual(result.note, "Typ zůstává")

    def test_update_rejects_change_to_other_inactive_type(self) -> None:
        relationship = self.create_base_relationship()
        inactive = self.make_type(
            "service_other_inactive",
            is_active=False,
        )

        with self.assertRaises(ValidationError) as context:
            update_relationship(
                relationship=relationship,
                data=self.make_data(relationship_type=inactive),
            )

        self.assert_error(
            context,
            key="relationship_type",
            code="relationship_type_inactive",
        )

    def test_update_compares_inactive_type_with_current_relationship(self) -> None:
        relationship = self.create_base_relationship()
        inactive = self.make_type(
            "service_current_comparison",
            is_active=False,
        )
        relationship.relationship_type_id = inactive.pk

        with self.assertRaises(ValidationError) as context:
            update_relationship(
                relationship=relationship,
                data=self.make_data(relationship_type=inactive),
            )

        self.assert_error(
            context,
            key="relationship_type",
            code="relationship_type_inactive",
        )

    def test_update_may_change_from_inactive_to_active_type(self) -> None:
        relationship = self.create_base_relationship()
        RelationshipType.objects.filter(pk=self.directional_type.pk).update(
            is_active=False
        )
        active = self.make_type("service_active_replacement")

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(relationship_type=active),
        )

        self.assertEqual(result.relationship_type_id, active.pk)

    def test_archived_relationship_can_be_updated(self) -> None:
        relationship = self.create_base_relationship()
        archived_at = timezone.now()
        Relationship.objects.filter(pk=relationship.pk).update(
            archived_at=archived_at,
            archive_reason="Archiv",
        )

        result = update_relationship(
            relationship=relationship,
            data=self.make_data(note="Opraveno"),
        )

        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archive_reason, "Archiv")
        self.assertEqual(result.note, "Opraveno")

    def test_soft_deleted_relationship_is_rejected(self) -> None:
        relationship = self.create_base_relationship()
        deleted_at = timezone.now()
        Relationship.objects.filter(pk=relationship.pk).update(
            deleted_at=deleted_at,
            deletion_reason="Odstraněno",
        )

        with self.assertRaises(ValidationError) as context:
            update_relationship(
                relationship=relationship,
                data=self.make_data(note="Zakázaná změna"),
            )

        self.assert_error(
            context,
            key="relationship",
            code="relationship_deleted",
        )
        relationship.refresh_from_db()
        self.assertEqual(relationship.deleted_at, deleted_at)
        self.assertEqual(relationship.deletion_reason, "Odstraněno")
        self.assertEqual(relationship.note, "")

    def test_archived_and_soft_deleted_people_are_allowed(self) -> None:
        Person.objects.filter(pk=self.person_a.pk).update(
            archived_at=timezone.now()
        )
        Person.objects.filter(pk=self.person_b.pk).update(
            deleted_at=timezone.now()
        )

        result = create_relationship(data=self.make_data())

        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)

    def test_uses_current_database_symmetry(self) -> None:
        stale_type = self.symmetric_type
        stale_type.is_symmetric = False

        result = create_relationship(
            data=self.make_data(
                relationship_type=stale_type,
                person_a=self.person_b,
                person_b=self.person_a,
            )
        )

        self.assertEqual(result.person_a_id, self.person_a.pk)
        self.assertEqual(result.person_b_id, self.person_b.pk)

    def test_relationship_to_self_keeps_model_error(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_relationship(
                data=self.make_data(person_b=self.person_a)
            )

        self.assert_error(
            context,
            key="person_b",
            code="relationship_to_self",
        )
        self.assertFalse(Relationship.objects.exists())

    def test_service_does_not_create_reverse_row(self) -> None:
        create_relationship(
            data=self.make_data(relationship_type=self.symmetric_type)
        )

        self.assertEqual(Relationship.objects.count(), 1)

    def test_supported_date_precisions_and_sort_dates(self) -> None:
        cases = (
            (
                "unknown",
                {},
                None,
                None,
            ),
            (
                "exact",
                {
                    "date_precision": DatePrecision.EXACT,
                    "start_year": 1980,
                    "start_month": 3,
                    "start_day": 4,
                },
                date(1980, 3, 4),
                date(1980, 3, 4),
            ),
            (
                "month",
                {
                    "date_precision": DatePrecision.MONTH,
                    "start_year": 1981,
                    "start_month": 2,
                },
                date(1981, 2, 1),
                date(1981, 2, 28),
            ),
            (
                "year",
                {
                    "date_precision": DatePrecision.YEAR,
                    "start_year": 1982,
                },
                date(1982, 1, 1),
                date(1982, 12, 31),
            ),
            (
                "range",
                {
                    "date_precision": DatePrecision.RANGE,
                    "start_year": 1983,
                    "end_year": 1984,
                },
                date(1983, 1, 1),
                date(1984, 12, 31),
            ),
        )
        for code, values, expected_start, expected_end in cases:
            with self.subTest(precision=code):
                relationship_type = self.make_type(
                    f"service_date_{code}",
                    supports_date_range=True,
                )
                result = create_relationship(
                    data=self.make_data(
                        relationship_type=relationship_type,
                        **values,
                    )
                )
                self.assertEqual(result.sort_date, expected_start)
                self.assertEqual(result.sort_date_end, expected_end)

    def test_range_is_rejected_when_type_does_not_support_it(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_relationship(
                data=self.make_data(
                    date_precision=DatePrecision.RANGE,
                    start_year=1900,
                    end_year=1910,
                )
            )

        self.assert_error(
            context,
            key="date_precision",
            code="date_range_not_supported",
        )

    def test_valid_date_qualifiers_are_preserved(self) -> None:
        for index, qualifier in enumerate(
            (
                DateQualifier.NONE,
                DateQualifier.APPROXIMATE,
                DateQualifier.BEFORE,
                DateQualifier.AFTER,
            ),
            start=1,
        ):
            with self.subTest(qualifier=qualifier):
                relationship_type = self.make_type(
                    f"service_qualifier_{index}"
                )
                result = create_relationship(
                    data=self.make_data(
                        relationship_type=relationship_type,
                        date_precision=DatePrecision.YEAR,
                        date_qualifier=qualifier,
                        start_year=1900 + index,
                    )
                )
                self.assertEqual(result.date_qualifier, qualifier)

    def test_duplicate_unknown_create_is_rejected(self) -> None:
        self.create_base_relationship()

        with self.assertRaises(ValidationError) as context:
            self.create_base_relationship(note="Jiná poznámka")

        self.assert_error(
            context,
            key=NON_FIELD_ERRORS,
            code="duplicate_relationship",
        )

    def test_duplicate_known_period_create_is_rejected(self) -> None:
        data = self.make_data(
            date_precision=DatePrecision.EXACT,
            start_year=1950,
            start_month=5,
            start_day=6,
        )
        create_relationship(data=data)

        with self.assertRaises(ValidationError) as context:
            create_relationship(data=data)

        self.assert_error(
            context,
            key=NON_FIELD_ERRORS,
            code="duplicate_relationship",
        )

    def test_different_period_is_allowed(self) -> None:
        first = self.make_data(
            date_precision=DatePrecision.YEAR,
            start_year=1950,
        )
        second = replace(first, start_year=1951)

        create_relationship(data=first)
        create_relationship(data=second)

        self.assertEqual(Relationship.objects.count(), 2)

    def test_update_into_duplicate_is_rejected_without_change(self) -> None:
        first_data = self.make_data(
            date_precision=DatePrecision.YEAR,
            start_year=1950,
        )
        second_data = replace(first_data, start_year=1951)
        create_relationship(data=first_data)
        second = create_relationship(data=second_data)

        with self.assertRaises(ValidationError) as context:
            update_relationship(relationship=second, data=first_data)

        self.assert_error(
            context,
            key=NON_FIELD_ERRORS,
            code="duplicate_relationship",
        )
        second.refresh_from_db()
        self.assertEqual(second.start_year, 1951)

    def test_archived_relationship_still_blocks_duplicate(self) -> None:
        relationship = self.create_base_relationship()
        Relationship.objects.filter(pk=relationship.pk).update(
            archived_at=timezone.now()
        )

        with self.assertRaises(ValidationError) as context:
            self.create_base_relationship()

        self.assert_error(
            context,
            key=NON_FIELD_ERRORS,
            code="duplicate_relationship",
        )

    def test_soft_deleted_relationship_does_not_block_replacement(self) -> None:
        relationship = self.create_base_relationship()
        Relationship.objects.filter(pk=relationship.pk).update(
            deleted_at=timezone.now()
        )

        replacement = self.create_base_relationship()

        self.assertNotEqual(replacement.pk, relationship.pk)
        self.assertEqual(Relationship.objects.count(), 2)

    def test_confirmed_integrity_conflict_becomes_duplicate_error(self) -> None:
        self.create_base_relationship()

        with patch.object(Relationship, "full_clean", return_value=None):
            with self.assertRaises(ValidationError) as context:
                self.create_base_relationship()

        self.assert_error(
            context,
            key=NON_FIELD_ERRORS,
            code="duplicate_relationship",
        )

    def test_unexpected_integrity_error_is_not_masked(self) -> None:
        with patch.object(
            Relationship,
            "save",
            side_effect=IntegrityError("neočekávaná integritní chyba"),
        ):
            with self.assertRaisesRegex(
                IntegrityError,
                "neočekávaná integritní chyba",
            ):
                self.create_base_relationship()

        self.assertFalse(Relationship.objects.exists())

    def test_check_constraint_integrity_error_is_not_masked(self) -> None:
        with patch.object(Relationship, "full_clean", return_value=None):
            with self.assertRaises(IntegrityError):
                create_relationship(
                    data=self.make_data(person_b=self.person_a)
                )

        self.assertFalse(Relationship.objects.exists())

    def test_foreign_key_integrity_error_is_not_masked(self) -> None:
        with patch.object(
            Relationship,
            "save",
            side_effect=IntegrityError("FOREIGN KEY constraint failed"),
        ):
            with self.assertRaisesRegex(
                IntegrityError,
                "FOREIGN KEY constraint failed",
            ):
                self.create_base_relationship()

        self.assertFalse(Relationship.objects.exists())

    def test_create_save_error_rolls_back_written_row(self) -> None:
        original_save = Relationship.save

        def save_then_fail(instance, *args, **kwargs) -> None:
            original_save(instance, *args, **kwargs)
            raise IntegrityError("chyba po zápisu")

        with patch.object(
            Relationship,
            "save",
            autospec=True,
            side_effect=save_then_fail,
        ):
            with self.assertRaisesRegex(IntegrityError, "chyba po zápisu"):
                self.create_base_relationship()

        self.assertFalse(Relationship.objects.exists())

    def test_update_save_error_rolls_back_and_keeps_input_object(self) -> None:
        relationship = self.create_base_relationship(note="Původní")
        original_save = Relationship.save

        def save_then_fail(instance, *args, **kwargs) -> None:
            original_save(instance, *args, **kwargs)
            raise IntegrityError("chyba změny")

        with patch.object(
            Relationship,
            "save",
            autospec=True,
            side_effect=save_then_fail,
        ):
            with self.assertRaisesRegex(IntegrityError, "chyba změny"):
                update_relationship(
                    relationship=relationship,
                    data=self.make_data(note="Neuložená"),
                )

        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Původní")

    def test_failed_full_clean_keeps_database_and_input_object(self) -> None:
        relationship = self.create_base_relationship(note="Původní")
        original_person_b_id = relationship.person_b_id

        with self.assertRaises(ValidationError):
            update_relationship(
                relationship=relationship,
                data=self.make_data(
                    person_b=self.person_a,
                    note="Neplatná",
                ),
            )

        self.assertEqual(relationship.note, "Původní")
        self.assertEqual(relationship.person_b_id, original_person_b_id)
        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Původní")
        self.assertEqual(relationship.person_b_id, original_person_b_id)

    def test_derivable_relationship_can_be_created_explicitly(self) -> None:
        sibling = self.make_type(
            "service_derivable_sibling",
            symmetric=True,
            is_derivable=True,
        )

        result = create_relationship(
            data=self.make_data(relationship_type=sibling)
        )

        self.assertEqual(result.relationship_type_id, sibling.pk)
        self.assertEqual(Relationship.objects.count(), 1)

    def test_service_does_not_check_parent_cycle(self) -> None:
        create_relationship(data=self.make_data())
        create_relationship(
            data=self.make_data(
                person_a=self.person_b,
                person_b=self.person_a,
            )
        )

        self.assertEqual(Relationship.objects.count(), 2)

    def test_service_does_not_check_overlapping_ranges(self) -> None:
        first = self.make_data(
            relationship_type=self.symmetric_type,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1910,
        )
        second = replace(first, start_year=1905, end_year=1915)

        create_relationship(data=first)
        create_relationship(data=second)

        self.assertEqual(Relationship.objects.count(), 2)


class ParentRelationshipCycleTests(TestCase):
    """Ověření společného grafu genealogických rodičovských vazeb."""

    parent_codes = (
        "biological_parent",
        "adoptive_parent",
        "step_parent",
        "foster_parent",
    )

    def setUp(self) -> None:
        self.people = [
            Person.objects.create(first_name=f"Osoba {index}")
            for index in range(1, 8)
        ]
        self.types = {
            code: RelationshipType.objects.get(code=code)
            for code in (
                *self.parent_codes,
                "guardian",
                "spouse",
                "partner",
                "sibling",
                "godparent",
                "family_friend",
                "other",
            )
        }

    def data(
        self,
        code: str,
        person_a: Person,
        person_b: Person,
        **changes: object,
    ) -> RelationshipInput:
        data = RelationshipInput(
            relationship_type=self.types[code],
            person_a=person_a,
            person_b=person_b,
        )
        return replace(data, **changes)

    def create_edge(
        self,
        code: str,
        person_a: Person,
        person_b: Person,
        **changes: object,
    ) -> Relationship:
        return create_relationship(
            data=self.data(code, person_a, person_b, **changes)
        )

    def assert_cycle_error(
        self,
        context,
        *,
        person_a: Person,
        person_b: Person,
        relationship_type: RelationshipType,
    ) -> None:
        self.assertIn("person_b", context.exception.error_dict)
        errors = context.exception.error_dict["person_b"]
        cycle_errors = [
            error
            for error in errors
            if error.code == "relationship_parent_cycle"
        ]
        self.assertEqual(len(cycle_errors), 1)
        self.assertEqual(
            cycle_errors[0].params,
            {
                "person_a_id": person_a.pk,
                "person_b_id": person_b.pk,
                "relationship_type_id": relationship_type.pk,
                "relationship_type_code": relationship_type.code,
            },
        )

    def test_parent_type_code_set_is_exact(self) -> None:
        self.assertEqual(
            services._PARENT_RELATIONSHIP_TYPE_CODES,
            frozenset(self.parent_codes),
        )

    def test_direct_cycle_is_rejected_with_stable_error(self) -> None:
        person_a, person_b = self.people[:2]
        self.create_edge("biological_parent", person_a, person_b)

        with self.assertRaises(ValidationError) as context:
            self.create_edge("biological_parent", person_b, person_a)

        self.assert_cycle_error(
            context,
            person_a=person_b,
            person_b=person_a,
            relationship_type=self.types["biological_parent"],
        )
        self.assertEqual(Relationship.objects.count(), 1)

    def test_three_node_cycle_is_rejected(self) -> None:
        person_a, person_b, person_c = self.people[:3]
        self.create_edge("biological_parent", person_a, person_b)
        self.create_edge("biological_parent", person_b, person_c)

        with self.assertRaises(ValidationError) as context:
            self.create_edge("biological_parent", person_c, person_a)

        self.assert_cycle_error(
            context,
            person_a=person_c,
            person_b=person_a,
            relationship_type=self.types["biological_parent"],
        )

    def test_cycle_longer_than_three_nodes_is_rejected(self) -> None:
        person_a, person_b, person_c, person_d, person_e = self.people[:5]
        self.create_edge("biological_parent", person_a, person_b)
        self.create_edge("biological_parent", person_b, person_c)
        self.create_edge("adoptive_parent", person_c, person_d)
        self.create_edge("step_parent", person_d, person_e)

        with self.assertRaises(ValidationError):
            self.create_edge("foster_parent", person_e, person_a)

        self.assertEqual(Relationship.objects.count(), 4)

    def test_valid_branched_tree_is_allowed(self) -> None:
        person_a, person_b, person_c, person_d, person_e, person_f = (
            self.people[:6]
        )
        self.create_edge("biological_parent", person_a, person_b)
        self.create_edge("adoptive_parent", person_a, person_c)
        self.create_edge("step_parent", person_b, person_d)
        self.create_edge("foster_parent", person_c, person_e)

        result = self.create_edge("biological_parent", person_d, person_f)

        self.assertEqual(result.person_a_id, person_d.pk)
        self.assertEqual(result.person_b_id, person_f.pk)
        self.assertEqual(Relationship.objects.count(), 5)

    def test_mixed_parent_types_share_one_graph(self) -> None:
        person_a, person_b, person_c, person_d = self.people[:4]
        self.create_edge("biological_parent", person_a, person_b)
        self.create_edge("adoptive_parent", person_b, person_c)
        self.create_edge("step_parent", person_c, person_d)

        with self.assertRaises(ValidationError) as context:
            self.create_edge("foster_parent", person_d, person_a)

        self.assert_cycle_error(
            context,
            person_a=person_d,
            person_b=person_a,
            relationship_type=self.types["foster_parent"],
        )

    def test_non_parent_system_types_do_not_enter_graph(self) -> None:
        for index, code in enumerate(
            (
                "guardian",
                "spouse",
                "partner",
                "sibling",
                "godparent",
                "family_friend",
                "other",
            )
        ):
            with self.subTest(code=code):
                person_a = Person.objects.create(
                    first_name=f"Výchozí {index}"
                )
                person_b = Person.objects.create(
                    first_name=f"Cílová {index}"
                )
                self.create_edge(code, person_b, person_a)

                result = self.create_edge(
                    "biological_parent",
                    person_a,
                    person_b,
                )

                self.assertEqual(result.person_a_id, person_a.pk)
                self.assertEqual(result.person_b_id, person_b.pk)

    def test_custom_parent_child_type_does_not_enter_graph(self) -> None:
        custom_type = RelationshipType.objects.create(
            code="service_custom_parent_child",
            name="Vlastní rodičovský typ",
            category="parent_child",
            forward_label_male="dítě",
            forward_label_female="dítě",
            forward_label_unknown="dítě",
            reverse_label_male="rodič",
            reverse_label_female="rodič",
            reverse_label_unknown="rodič",
        )
        person_a, person_b = self.people[:2]
        create_relationship(
            data=RelationshipInput(
                relationship_type=custom_type,
                person_a=person_b,
                person_b=person_a,
            )
        )

        result = self.create_edge("biological_parent", person_a, person_b)

        self.assertEqual(result.person_a_id, person_a.pk)
        self.assertEqual(Relationship.objects.count(), 2)

    def test_update_person_a_that_creates_cycle_is_rejected(self) -> None:
        person_a, person_b, person_c = self.people[:3]
        self.create_edge("biological_parent", person_a, person_b)
        relationship = self.create_edge(
            "biological_parent",
            person_c,
            person_a,
        )

        with self.assertRaises(ValidationError) as context:
            update_relationship(
                relationship=relationship,
                data=self.data(
                    "biological_parent",
                    person_b,
                    person_a,
                ),
            )

        self.assert_cycle_error(
            context,
            person_a=person_b,
            person_b=person_a,
            relationship_type=self.types["biological_parent"],
        )
        relationship.refresh_from_db()
        self.assertEqual(relationship.person_a_id, person_c.pk)

    def test_update_person_b_that_creates_cycle_is_rejected(self) -> None:
        person_a, person_b, person_c = self.people[:3]
        self.create_edge("biological_parent", person_a, person_b)
        relationship = self.create_edge(
            "biological_parent",
            person_b,
            person_c,
        )

        with self.assertRaises(ValidationError):
            update_relationship(
                relationship=relationship,
                data=self.data(
                    "biological_parent",
                    person_b,
                    person_a,
                ),
            )

        relationship.refresh_from_db()
        self.assertEqual(relationship.person_b_id, person_c.pk)

    def test_update_to_parent_type_that_creates_cycle_is_rejected(self) -> None:
        person_a, person_b = self.people[:2]
        self.create_edge("biological_parent", person_a, person_b)
        relationship = self.create_edge("guardian", person_b, person_a)

        with self.assertRaises(ValidationError):
            update_relationship(
                relationship=relationship,
                data=self.data(
                    "adoptive_parent",
                    person_b,
                    person_a,
                ),
            )

        relationship.refresh_from_db()
        self.assertEqual(
            relationship.relationship_type_id,
            self.types["guardian"].pk,
        )

    def test_update_parent_to_non_parent_can_remove_old_cycle(self) -> None:
        person_a, person_b = self.people[:2]
        self.create_edge("biological_parent", person_a, person_b)
        relationship = Relationship.objects.create(
            relationship_type=self.types["adoptive_parent"],
            person_a=person_b,
            person_b=person_a,
        )

        result = update_relationship(
            relationship=relationship,
            data=self.data("guardian", person_b, person_a),
        )

        self.assertEqual(result.pk, relationship.pk)
        self.assertEqual(
            result.relationship_type_id,
            self.types["guardian"].pk,
        )

    def test_update_excludes_current_relationship_from_graph(self) -> None:
        person_a, person_b = self.people[:2]
        relationship = self.create_edge(
            "biological_parent",
            person_a,
            person_b,
        )

        result = update_relationship(
            relationship=relationship,
            data=self.data(
                "biological_parent",
                person_b,
                person_a,
            ),
        )

        self.assertEqual(result.pk, relationship.pk)
        self.assertEqual(result.person_a_id, person_b.pk)
        self.assertEqual(result.person_b_id, person_a.pk)

    def test_archived_parent_edge_still_blocks_cycle(self) -> None:
        person_a, person_b = self.people[:2]
        relationship = self.create_edge(
            "biological_parent",
            person_a,
            person_b,
        )
        Relationship.objects.filter(pk=relationship.pk).update(
            archived_at=timezone.now()
        )

        with self.assertRaises(ValidationError):
            self.create_edge("adoptive_parent", person_b, person_a)

    def test_soft_deleted_parent_edge_does_not_block_cycle(self) -> None:
        person_a, person_b = self.people[:2]
        relationship = self.create_edge(
            "biological_parent",
            person_a,
            person_b,
        )
        Relationship.objects.filter(pk=relationship.pk).update(
            deleted_at=timezone.now()
        )

        result = self.create_edge("adoptive_parent", person_b, person_a)

        self.assertEqual(result.person_a_id, person_b.pk)

    def test_unknown_exact_and_historical_range_edges_are_included(self) -> None:
        cases = (
            ("unknown", "biological_parent", {}),
            (
                "exact",
                "adoptive_parent",
                {
                    "date_precision": DatePrecision.EXACT,
                    "start_year": 1900,
                    "start_month": 1,
                    "start_day": 2,
                },
            ),
            (
                "range",
                "step_parent",
                {
                    "date_precision": DatePrecision.RANGE,
                    "start_year": 1900,
                    "end_year": 1910,
                },
            ),
        )
        for index, (name, code, values) in enumerate(cases):
            with self.subTest(precision=name):
                person_a = Person.objects.create(
                    first_name=f"Rodič času {index}"
                )
                person_b = Person.objects.create(
                    first_name=f"Dítě času {index}"
                )
                self.create_edge(code, person_a, person_b, **values)

                with self.assertRaises(ValidationError):
                    self.create_edge(
                        "foster_parent",
                        person_b,
                        person_a,
                    )

    def test_inactive_type_does_not_remove_existing_edge(self) -> None:
        person_a, person_b = self.people[:2]
        self.create_edge("biological_parent", person_a, person_b)
        RelationshipType.objects.filter(
            pk=self.types["biological_parent"].pk
        ).update(is_active=False)

        with self.assertRaises(ValidationError):
            self.create_edge("adoptive_parent", person_b, person_a)

    def test_older_unrelated_cycle_does_not_block_new_edge(self) -> None:
        person_a, person_b, person_c, person_d = self.people[:4]
        Relationship.objects.create(
            relationship_type=self.types["biological_parent"],
            person_a=person_a,
            person_b=person_b,
        )
        Relationship.objects.create(
            relationship_type=self.types["adoptive_parent"],
            person_a=person_b,
            person_b=person_a,
        )

        result = self.create_edge(
            "biological_parent",
            person_c,
            person_d,
        )

        self.assertEqual(result.person_a_id, person_c.pk)

    def test_visited_handles_old_cycle_reached_by_valid_candidate(self) -> None:
        person_a, person_b, person_c = self.people[:3]
        Relationship.objects.create(
            relationship_type=self.types["biological_parent"],
            person_a=person_a,
            person_b=person_b,
        )
        Relationship.objects.create(
            relationship_type=self.types["adoptive_parent"],
            person_a=person_b,
            person_b=person_a,
        )

        result = self.create_edge(
            "foster_parent",
            person_c,
            person_a,
        )

        self.assertEqual(result.person_a_id, person_c.pk)
        self.assertEqual(result.person_b_id, person_a.pk)

    def test_candidate_closing_path_in_old_graph_is_rejected(self) -> None:
        person_a, person_b, person_c = self.people[:3]
        Relationship.objects.create(
            relationship_type=self.types["biological_parent"],
            person_a=person_a,
            person_b=person_b,
        )
        Relationship.objects.create(
            relationship_type=self.types["adoptive_parent"],
            person_a=person_b,
            person_b=person_a,
        )
        self.create_edge("step_parent", person_c, person_a)

        with self.assertRaises(ValidationError):
            self.create_edge("foster_parent", person_b, person_c)

    def test_parent_self_relationship_keeps_model_error(self) -> None:
        person = self.people[0]

        with self.assertRaises(ValidationError) as context:
            self.create_edge("biological_parent", person, person)

        errors = context.exception.error_dict["person_b"]
        self.assertIn(
            "relationship_to_self",
            [error.code for error in errors],
        )
        self.assertNotIn(
            "relationship_parent_cycle",
            [error.code for error in errors],
        )

    def test_cycle_validation_loads_graph_with_one_queryset(self) -> None:
        person_a, person_b = self.people[:2]

        with patch.object(
            Relationship.objects,
            "select_for_update",
            wraps=Relationship.objects.select_for_update,
        ) as graph_lock:
            self.create_edge("biological_parent", person_a, person_b)

        graph_lock.assert_called_once_with()

    def test_non_parent_type_skips_graph_query(self) -> None:
        person_a, person_b = self.people[:2]

        with patch.object(
            Relationship.objects,
            "select_for_update",
            wraps=Relationship.objects.select_for_update,
        ) as graph_lock:
            self.create_edge("guardian", person_a, person_b)

        graph_lock.assert_not_called()
