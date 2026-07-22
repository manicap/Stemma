from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, timedelta
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from events.models import Event
from people.models import Person

from . import services
from .models import Place, Residence, ResidenceType
from .services import (
    ResidenceInput,
    create_residence,
    update_residence,
)


class ResidenceServiceApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu služby bydlišť."""

    def test_module_exports_only_approved_public_api(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "ResidenceInput",
                "create_residence",
                "update_residence",
            ),
        )

    def test_input_is_frozen_slotted_dataclass(self) -> None:
        data = ResidenceInput(
            person=Person(),
            residence_type=ResidenceType(),
        )

        self.assertFalse(hasattr(data, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            data.note = "Změna"

    def test_input_has_exact_fields_in_order(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(ResidenceInput)),
            (
                "person",
                "residence_type",
                "place",
                "address_text",
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
        data = ResidenceInput(
            person=Person(),
            residence_type=ResidenceType(),
        )

        self.assertIsNone(data.place)
        self.assertEqual(data.address_text, "")
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
        parameters = signature(create_residence).parameters

        self.assertEqual(tuple(parameters), ("data", "created_by"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )

    def test_update_contract_is_keyword_only(self) -> None:
        parameters = signature(update_residence).parameters

        self.assertEqual(tuple(parameters), ("residence", "data"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class ResidenceServiceTests(TestCase):
    """Integrační testy vytvoření a změny jednotlivého bydliště."""

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="První",
        )
        self.other_person = Person.objects.create(
            first_name="Bohumil",
            last_name="Druhý",
        )
        self.residence_type = self.make_type("service_primary")
        self.other_type = self.make_type("service_other")
        self.place = self.make_place("Praha")
        self.other_place = self.make_place("Brno")

    @staticmethod
    def make_type(
        code: str,
        *,
        is_active: bool = True,
        is_system: bool = False,
    ) -> ResidenceType:
        return ResidenceType.objects.create(
            code=code,
            name=code,
            is_active=is_active,
            is_system=is_system,
        )

    @staticmethod
    def make_place(name: str) -> Place:
        return Place.objects.create(
            name=name,
            normalized_name=name.casefold(),
        )

    def make_data(self, **changes: object) -> ResidenceInput:
        data = ResidenceInput(
            person=self.person,
            residence_type=self.residence_type,
            place=self.place,
        )
        return replace(data, **changes)

    def create_base_residence(self, **changes: object) -> Residence:
        return create_residence(data=self.make_data(**changes))

    def create_direct_residence(
        self,
        *,
        residence_type: ResidenceType,
        created_by=None,
    ) -> Residence:
        return Residence.objects.create(
            person=self.person,
            residence_type=residence_type,
            place=self.place,
            created_by=created_by,
        )

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

    def test_create_with_place_only(self) -> None:
        result = create_residence(data=self.make_data())

        self.assertIsInstance(result, Residence)
        self.assertEqual(result.place_id, self.place.pk)
        self.assertEqual(result.address_text, "")
        self.assertEqual(Residence.objects.count(), 1)

    def test_create_with_address_only(self) -> None:
        result = create_residence(
            data=self.make_data(place=None, address_text="Historická 12")
        )

        self.assertIsNone(result.place_id)
        self.assertEqual(result.address_text, "Historická 12")

    def test_create_with_place_and_address(self) -> None:
        result = create_residence(
            data=self.make_data(address_text="Staré Město 12")
        )

        self.assertEqual(result.place_id, self.place.pk)
        self.assertEqual(result.address_text, "Staré Město 12")

    def test_create_transfers_all_editable_values_and_created_by(self) -> None:
        creator = get_user_model().objects.create_user(
            username="residence-creator"
        )
        data = self.make_data(
            person=self.other_person,
            residence_type=self.other_type,
            place=self.other_place,
            address_text="Květná 5",
            note="Doložený pobyt",
            access_level=AccessLevel.RESTRICTED,
            verification_status=VerificationStatus.VERIFIED,
            date_precision=DatePrecision.RANGE,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1901,
            start_month=2,
            start_day=3,
            end_year=1903,
            end_month=4,
            end_day=5,
            original_date_text="asi 1901–1903",
            date_note="Rozmezí podle pramene",
        )

        result = create_residence(data=data, created_by=creator)

        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.residence_type_id, self.other_type.pk)
        self.assertEqual(result.place_id, self.other_place.pk)
        self.assertEqual(result.address_text, "Květná 5")
        self.assertEqual(result.note, "Doložený pobyt")
        self.assertEqual(result.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.created_by_id, creator.pk)
        self.assertEqual(result.date_precision, DatePrecision.RANGE)
        self.assertEqual(
            result.date_qualifier,
            DateQualifier.APPROXIMATE,
        )
        self.assertEqual(result.start_year, 1901)
        self.assertEqual(result.start_month, 2)
        self.assertEqual(result.start_day, 3)
        self.assertEqual(result.end_year, 1903)
        self.assertEqual(result.end_month, 4)
        self.assertEqual(result.end_day, 5)
        self.assertEqual(result.original_date_text, "asi 1901–1903")
        self.assertEqual(result.date_note, "Rozmezí podle pramene")
        self.assertEqual(result.sort_date, date(1901, 2, 3))
        self.assertEqual(result.sort_date_end, date(1903, 4, 5))

    def test_create_allows_created_by_none_and_uses_defaults(self) -> None:
        result = create_residence(data=self.make_data())

        self.assertIsNone(result.created_by_id)
        self.assertEqual(result.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(result.date_precision, DatePrecision.UNKNOWN)
        self.assertEqual(result.date_qualifier, DateQualifier.NONE)
        self.assertIsNone(result.archived_at)
        self.assertIsNone(result.deleted_at)

    def test_create_returns_fresh_select_related_residence(self) -> None:
        result = create_residence(data=self.make_data())

        self.assertFalse(result._state.adding)
        self.assertEqual(
            set(result._state.fields_cache),
            {"person", "residence_type", "place", "created_by"},
        )

    def test_service_strips_only_outer_text_whitespace(self) -> None:
        result = create_residence(
            data=self.make_data(
                place=None,
                address_text="  Nová   ulice 12  ",
                note="  dvě   mezery  ",
                original_date_text="  kolem   1900  ",
                date_note="  zápis   v matrice  ",
            )
        )

        self.assertEqual(result.address_text, "Nová   ulice 12")
        self.assertEqual(result.note, "dvě   mezery")
        self.assertEqual(result.original_date_text, "kolem   1900")
        self.assertEqual(result.date_note, "zápis   v matrice")

    def test_model_save_outside_service_does_not_strip_text(self) -> None:
        residence = Residence.objects.create(
            person=self.person,
            residence_type=self.residence_type,
            address_text="  Beze změny  ",
            note="  Poznámka  ",
        )
        residence.refresh_from_db()

        self.assertEqual(residence.address_text, "  Beze změny  ")
        self.assertEqual(residence.note, "  Poznámka  ")

    def test_create_location_error_rolls_back(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_residence(
                data=self.make_data(place=None, address_text="  \t ")
            )

        self.assert_error(
            context,
            key="address_text",
            code="residence_location_required",
        )
        self.assertEqual(Residence.objects.count(), 0)

    def test_partial_date_unknown_is_default(self) -> None:
        result = create_residence(data=self.make_data())

        self.assertEqual(result.date_precision, DatePrecision.UNKNOWN)
        self.assertIsNone(result.sort_date)
        self.assertIsNone(result.sort_date_end)

    def test_create_accepts_valid_partial_year(self) -> None:
        result = create_residence(
            data=self.make_data(
                date_precision=DatePrecision.YEAR,
                start_year=1901,
            )
        )

        self.assertEqual(result.sort_date, date(1901, 1, 1))
        self.assertEqual(result.sort_date_end, date(1901, 12, 31))

    def test_create_accepts_valid_range(self) -> None:
        result = create_residence(
            data=self.make_data(
                date_precision=DatePrecision.RANGE,
                start_year=1901,
                end_year=1903,
            )
        )

        self.assertEqual(result.sort_date, date(1901, 1, 1))
        self.assertEqual(result.sort_date_end, date(1903, 12, 31))

    def test_invalid_partial_date_rolls_back_create(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_residence(
                data=self.make_data(
                    date_precision=DatePrecision.EXACT,
                    start_year=1901,
                )
            )

        self.assert_error(context, key="start_month", code="missing_month")
        self.assertEqual(Residence.objects.count(), 0)

    def test_create_accepts_explicit_access_and_verification(self) -> None:
        result = create_residence(
            data=self.make_data(
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.DISPUTED,
            )
        )

        self.assertEqual(result.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.DISPUTED,
        )

    def test_invalid_access_or_verification_fails_full_clean(self) -> None:
        for field_name in ("access_level", "verification_status"):
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValidationError) as context:
                    create_residence(
                        data=self.make_data(**{field_name: "invalid"})
                    )
                self.assertIn(field_name, context.exception.error_dict)
        self.assertEqual(Residence.objects.count(), 0)

    def test_rejects_unsaved_person(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_residence(
                data=self.make_data(person=Person(first_name="Nová"))
            )

        self.assert_error(
            context,
            key="person",
            code="residence_person_unsaved",
        )

    def test_rejects_physically_missing_person(self) -> None:
        missing = Person.objects.create(first_name="Odstraněná")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data(person=missing))

        self.assert_error(
            context,
            key="person",
            code="residence_person_unsaved",
        )

    def test_rejects_unsaved_residence_type(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_residence(
                data=self.make_data(
                    residence_type=ResidenceType(name="Nový")
                )
            )

        self.assert_error(
            context,
            key="residence_type",
            code="residence_type_unsaved",
        )

    def test_rejects_physically_missing_residence_type(self) -> None:
        missing = self.make_type("service_missing_type")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data(residence_type=missing))

        self.assert_error(
            context,
            key="residence_type",
            code="residence_type_unsaved",
        )

    def test_rejects_unsaved_place(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_residence(
                data=self.make_data(
                    place=Place(name="Nové", normalized_name="nove")
                )
            )

        self.assert_error(
            context,
            key="place",
            code="residence_place_unsaved",
        )

    def test_rejects_physically_missing_place(self) -> None:
        missing = self.make_place("Odstraněné")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data(place=missing))

        self.assert_error(
            context,
            key="place",
            code="residence_place_unsaved",
        )

    def test_rejects_unsaved_created_by(self) -> None:
        creator = get_user_model()(username="unsaved-residence-author")

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data(), created_by=creator)

        self.assert_error(
            context,
            key="created_by",
            code="residence_created_by_unsaved",
        )

    def test_rejects_physically_missing_created_by(self) -> None:
        creator = get_user_model().objects.create_user(
            username="missing-residence-author"
        )
        creator_pk = creator.pk
        creator.delete()
        creator.pk = creator_pk

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data(), created_by=creator)

        self.assert_error(
            context,
            key="created_by",
            code="residence_created_by_unsaved",
        )

    def test_create_uses_current_inactive_type_state(self) -> None:
        ResidenceType.objects.filter(pk=self.residence_type.pk).update(
            is_active=False
        )
        self.assertTrue(self.residence_type.is_active)

        with self.assertRaises(ValidationError) as context:
            create_residence(data=self.make_data())

        self.assert_error(
            context,
            key="residence_type",
            code="residence_type_inactive",
        )
        self.assertEqual(Residence.objects.count(), 0)

    def test_update_replaces_complete_snapshot_including_person(self) -> None:
        residence = self.create_base_residence(address_text="Původní")

        result = update_residence(
            residence=residence,
            data=self.make_data(
                person=self.other_person,
                residence_type=self.other_type,
                place=self.other_place,
                address_text="Nová 7",
                note="Nová poznámka",
                access_level=AccessLevel.AUTHENTICATED,
                verification_status=VerificationStatus.PROBABLE,
                date_precision=DatePrecision.EXACT,
                date_qualifier=DateQualifier.BEFORE,
                start_year=1910,
                start_month=5,
                start_day=6,
                original_date_text="před 6. 5. 1910",
                date_note="Přepsáno",
            ),
        )

        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.residence_type_id, self.other_type.pk)
        self.assertEqual(result.place_id, self.other_place.pk)
        self.assertEqual(result.address_text, "Nová 7")
        self.assertEqual(result.note, "Nová poznámka")
        self.assertEqual(result.access_level, AccessLevel.AUTHENTICATED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.PROBABLE,
        )
        self.assertEqual(result.date_precision, DatePrecision.EXACT)
        self.assertEqual(result.date_qualifier, DateQualifier.BEFORE)
        self.assertEqual(result.sort_date, date(1910, 5, 6))
        self.assertEqual(result.original_date_text, "před 6. 5. 1910")
        self.assertEqual(result.date_note, "Přepsáno")

    def test_update_can_remove_place_when_address_remains(self) -> None:
        residence = self.create_base_residence()

        result = update_residence(
            residence=residence,
            data=self.make_data(place=None, address_text="Neurčená obec"),
        )

        self.assertIsNone(result.place_id)
        self.assertEqual(result.address_text, "Neurčená obec")

    def test_update_normalizes_texts(self) -> None:
        residence = self.create_base_residence()

        result = update_residence(
            residence=residence,
            data=self.make_data(
                address_text="  Nová   7  ",
                note="  Poznámka  ",
                original_date_text="  asi   1900  ",
                date_note="  nejisté  ",
            ),
        )

        self.assertEqual(result.address_text, "Nová   7")
        self.assertEqual(result.note, "Poznámka")
        self.assertEqual(result.original_date_text, "asi   1900")
        self.assertEqual(result.date_note, "nejisté")

    def test_update_location_error_rolls_back_original_values(self) -> None:
        residence = self.create_base_residence(address_text="Původní")
        original_updated_at = residence.updated_at

        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=residence,
                data=self.make_data(
                    person=self.other_person,
                    place=None,
                    address_text="   ",
                    note="Neuložit",
                ),
            )

        self.assert_error(
            context,
            key="address_text",
            code="residence_location_required",
        )
        residence.refresh_from_db()
        self.assertEqual(residence.person_id, self.person.pk)
        self.assertEqual(residence.place_id, self.place.pk)
        self.assertEqual(residence.address_text, "Původní")
        self.assertEqual(residence.note, "")
        self.assertEqual(residence.updated_at, original_updated_at)

    def test_invalid_date_rolls_back_update(self) -> None:
        residence = self.create_base_residence(
            address_text="Původní",
            date_precision=DatePrecision.YEAR,
            start_year=1901,
        )
        original_updated_at = residence.updated_at

        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=residence,
                data=self.make_data(
                    place=self.other_place,
                    address_text="Nová",
                    date_precision=DatePrecision.RANGE,
                    start_year=1910,
                    end_year=1900,
                ),
            )

        self.assert_error(
            context,
            key="end_year",
            code="range_end_before_start",
        )
        residence.refresh_from_db()
        self.assertEqual(residence.place_id, self.place.pk)
        self.assertEqual(residence.address_text, "Původní")
        self.assertEqual(residence.date_precision, DatePrecision.YEAR)
        self.assertEqual(residence.start_year, 1901)
        self.assertEqual(residence.updated_at, original_updated_at)

    def test_update_keeps_same_inactive_type(self) -> None:
        inactive = self.make_type("service_inactive_same", is_active=False)
        residence = self.create_direct_residence(residence_type=inactive)

        result = update_residence(
            residence=residence,
            data=self.make_data(residence_type=inactive, note="Doplněno"),
        )

        self.assertEqual(result.residence_type_id, inactive.pk)
        self.assertEqual(result.note, "Doplněno")

    def test_update_rejects_active_to_other_inactive_type(self) -> None:
        inactive = self.make_type("service_inactive_target", is_active=False)
        residence = self.create_base_residence()

        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=residence,
                data=self.make_data(residence_type=inactive),
            )

        self.assert_error(
            context,
            key="residence_type",
            code="residence_type_inactive",
        )

    def test_update_rejects_inactive_to_other_inactive_type(self) -> None:
        current = self.make_type("service_inactive_current", is_active=False)
        target = self.make_type("service_inactive_other", is_active=False)
        residence = self.create_direct_residence(residence_type=current)

        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=residence,
                data=self.make_data(residence_type=target),
            )

        self.assert_error(
            context,
            key="residence_type",
            code="residence_type_inactive",
        )

    def test_update_allows_inactive_to_active_type(self) -> None:
        inactive = self.make_type("service_inactive_old", is_active=False)
        residence = self.create_direct_residence(residence_type=inactive)

        result = update_residence(
            residence=residence,
            data=self.make_data(residence_type=self.other_type),
        )

        self.assertEqual(result.residence_type_id, self.other_type.pk)

    def test_update_compares_inactive_type_by_primary_key(self) -> None:
        inactive = self.make_type("service_inactive_pk", is_active=False)
        same_pk_instance = ResidenceType(pk=inactive.pk, is_active=True)
        residence = self.create_direct_residence(residence_type=inactive)

        result = update_residence(
            residence=residence,
            data=self.make_data(residence_type=same_pk_instance),
        )

        self.assertEqual(result.residence_type_id, inactive.pk)

    def test_update_uses_current_residence_type_for_transition(self) -> None:
        inactive = self.make_type("service_current_inactive", is_active=False)
        residence = self.create_base_residence()
        Residence.objects.filter(pk=residence.pk).update(
            residence_type=inactive
        )
        self.assertEqual(residence.residence_type_id, self.residence_type.pk)

        result = update_residence(
            residence=residence,
            data=self.make_data(residence_type=inactive, note="Povoleno"),
        )

        self.assertEqual(result.residence_type_id, inactive.pk)

    def test_update_preserves_created_by_created_at_and_lifecycle(self) -> None:
        creator = get_user_model().objects.create_user(username="creator")
        archivist = get_user_model().objects.create_user(
            username="residence-archivist"
        )
        residence = create_residence(
            data=self.make_data(),
            created_by=creator,
        )
        archived_at = timezone.now() - timedelta(days=1)
        Residence.objects.filter(pk=residence.pk).update(
            archived_at=archived_at,
            archived_by=archivist,
            archive_reason="Historický záznam",
        )
        created_at = residence.created_at

        result = update_residence(
            residence=residence,
            data=self.make_data(note="Doplněno"),
        )

        self.assertEqual(result.created_by_id, creator.pk)
        self.assertEqual(result.created_at, created_at)
        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archived_by_id, archivist.pk)
        self.assertEqual(result.archive_reason, "Historický záznam")
        self.assertIsNone(result.deleted_at)
        self.assertIsNone(result.deleted_by_id)
        self.assertEqual(result.deletion_reason, "")

    def test_update_refreshes_updated_at(self) -> None:
        residence = self.create_base_residence()
        changed_at = residence.updated_at + timedelta(days=1)

        with patch("django.utils.timezone.now", return_value=changed_at):
            result = update_residence(
                residence=residence,
                data=self.make_data(note="Později"),
            )

        self.assertEqual(result.updated_at, changed_at)

    def test_update_rejects_soft_deleted_current_residence(self) -> None:
        residence = self.create_base_residence(note="Původní")
        deleted_at = timezone.now()
        Residence.objects.filter(pk=residence.pk).update(
            deleted_at=deleted_at
        )

        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=residence,
                data=self.make_data(note="Neuložit"),
            )

        self.assert_error(
            context,
            key="residence",
            code="residence_deleted",
        )
        residence.refresh_from_db()
        self.assertEqual(residence.note, "Původní")
        self.assertEqual(residence.deleted_at, deleted_at)

    def test_update_rejects_unsaved_residence(self) -> None:
        with self.assertRaises(ValidationError) as context:
            update_residence(
                residence=Residence(),
                data=self.make_data(),
            )

        self.assert_error(
            context,
            key="residence",
            code="residence_unsaved",
        )

    def test_update_rejects_physically_missing_residence(self) -> None:
        residence = self.create_base_residence()
        residence_pk = residence.pk
        residence.delete()
        residence.pk = residence_pk

        with self.assertRaises(ValidationError) as context:
            update_residence(residence=residence, data=self.make_data())

        self.assert_error(
            context,
            key="residence",
            code="residence_unsaved",
        )

    def test_update_preserves_fresh_created_by_not_stale_instance(self) -> None:
        original_creator = get_user_model().objects.create_user(
            username="original-creator"
        )
        current_creator = get_user_model().objects.create_user(
            username="current-creator"
        )
        residence = create_residence(
            data=self.make_data(),
            created_by=original_creator,
        )
        Residence.objects.filter(pk=residence.pk).update(
            created_by=current_creator
        )
        self.assertEqual(residence.created_by_id, original_creator.pk)

        result = update_residence(
            residence=residence,
            data=self.make_data(note="Změněno"),
        )

        self.assertEqual(result.created_by_id, current_creator.pk)

    def test_create_uses_fresh_person_state(self) -> None:
        Person.objects.filter(pk=self.person.pk).update(first_name="Aktuální")
        self.assertEqual(self.person.first_name, "Anna")

        result = create_residence(data=self.make_data())

        self.assertEqual(result.person.first_name, "Aktuální")

    def test_active_user_type_is_allowed_for_create_and_update(self) -> None:
        user_type = self.make_type("service_user_type", is_system=False)
        residence = create_residence(
            data=self.make_data(residence_type=user_type)
        )

        result = update_residence(
            residence=residence,
            data=self.make_data(residence_type=user_type, note="Upraveno"),
        )

        self.assertEqual(result.residence_type_id, user_type.pk)
        self.assertEqual(result.note, "Upraveno")

    def test_archived_and_soft_deleted_people_and_places_are_allowed(
        self,
    ) -> None:
        now = timezone.now()
        Person.objects.filter(pk=self.person.pk).update(archived_at=now)
        Place.objects.filter(pk=self.place.pk).update(deleted_at=now)

        result = create_residence(data=self.make_data())

        self.assertEqual(result.person_id, self.person.pk)
        self.assertEqual(result.place_id, self.place.pk)

    def test_service_allows_two_similar_residences(self) -> None:
        first = create_residence(data=self.make_data())
        second = create_residence(data=self.make_data())

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(Residence.objects.count(), 2)

    def test_service_has_no_unplanned_side_writes(self) -> None:
        creator = get_user_model().objects.create_user(
            username="side-effect-check"
        )
        person_values = (self.person.first_name, self.person.last_name)
        type_values = (
            self.residence_type.name,
            self.residence_type.is_active,
        )
        place_values = (self.place.name, self.place.normalized_name)
        event_count = Event.objects.count()

        create_residence(data=self.make_data(), created_by=creator)

        self.person.refresh_from_db()
        self.residence_type.refresh_from_db()
        self.place.refresh_from_db()
        creator.refresh_from_db()
        self.assertEqual(
            (self.person.first_name, self.person.last_name),
            person_values,
        )
        self.assertEqual(
            (self.residence_type.name, self.residence_type.is_active),
            type_values,
        )
        self.assertEqual(
            (self.place.name, self.place.normalized_name),
            place_values,
        )
        self.assertEqual(creator.username, "side-effect-check")
        self.assertEqual(Event.objects.count(), event_count)
        self.assertEqual(Residence.objects.count(), 1)

    def test_update_uses_select_for_update_on_residence(self) -> None:
        residence = self.create_base_residence()

        with patch.object(
            Residence.objects,
            "select_for_update",
            wraps=Residence.objects.select_for_update,
        ) as mocked_lock:
            update_residence(
                residence=residence,
                data=self.make_data(note="Uzamčeno"),
            )

        mocked_lock.assert_called()

    def test_unexpected_integrity_error_is_not_mapped(self) -> None:
        with patch.object(
            Residence,
            "save",
            side_effect=IntegrityError("Simulovaná databázová chyba"),
        ):
            with self.assertRaises(IntegrityError) as context:
                create_residence(data=self.make_data())

        self.assertEqual(
            str(context.exception),
            "Simulovaná databázová chyba",
        )
        self.assertEqual(Residence.objects.count(), 0)
