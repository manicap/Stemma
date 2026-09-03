from dataclasses import FrozenInstanceError, fields, replace
from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from people.models import Person
from places.models import Place

from . import services
from .models import HealthRecord, HealthRecordType
from .services import (
    HealthRecordInput,
    create_health_record,
    update_health_record,
)


class HealthRecordServiceApiTests(SimpleTestCase):
    def test_public_api_and_keyword_only_contracts_are_exact(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "HealthRecordInput",
                "create_health_record",
                "update_health_record",
            ),
        )
        self.assertEqual(
            tuple(signature(create_health_record).parameters),
            ("data", "created_by"),
        )
        self.assertEqual(
            tuple(signature(update_health_record).parameters),
            ("health_record", "data"),
        )
        for function in (create_health_record, update_health_record):
            self.assertTrue(
                all(
                    value.kind is Parameter.KEYWORD_ONLY
                    for value in signature(function).parameters.values()
                )
            )

    def test_input_is_frozen_slotted_and_defaults_to_restricted(self) -> None:
        data = HealthRecordInput(person=Person(), record_type=HealthRecordType())

        self.assertFalse(hasattr(data, "__dict__"))
        self.assertEqual(data.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            data.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        with self.assertRaises(FrozenInstanceError):
            data.title = "Změna"
        self.assertEqual(
            tuple(field.name for field in fields(HealthRecordInput)),
            (
                "person", "record_type", "place", "title", "description",
                "provider_name", "note", "access_level",
                "verification_status", "date_precision", "date_qualifier",
                "start_year", "start_month", "start_day", "end_year",
                "end_month", "end_day", "original_date_text", "date_note",
            ),
        )


class HealthRecordServiceTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Anna", last_name="První")
        self.other_person = Person.objects.create(
            first_name="Berta",
            last_name="Druhá",
        )
        self.record_type = HealthRecordType.objects.create(
            code="exam",
            name="Vyšetření",
        )
        self.other_type = HealthRecordType.objects.create(
            code="other",
            name="Jiné",
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )

    def make_data(self, **changes) -> HealthRecordInput:
        data = HealthRecordInput(
            person=self.person,
            record_type=self.record_type,
            title="Kontrola",
        )
        return replace(data, **changes)

    def assert_error(self, context, key: str, code: str) -> None:
        self.assertIn(
            code,
            {error.code for error in context.exception.error_dict[key]},
        )

    def test_create_persists_full_snapshot_and_strips_text(self) -> None:
        creator = get_user_model().objects.create_user(username="creator")
        result = create_health_record(
            data=self.make_data(
                person=self.other_person,
                record_type=self.other_type,
                place=self.place,
                title="  Kontrola  ",
                description="  Popis  ",
                provider_name="  MUDr. Novák  ",
                note="  Poznámka  ",
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.VERIFIED,
                date_precision=DatePrecision.YEAR,
                start_year=1998,
                original_date_text="  asi 1998  ",
                date_note="  podle zprávy  ",
            ),
            created_by=creator,
        )

        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.record_type_id, self.other_type.pk)
        self.assertEqual(result.place_id, self.place.pk)
        self.assertEqual(result.title, "Kontrola")
        self.assertEqual(result.description, "Popis")
        self.assertEqual(result.provider_name, "MUDr. Novák")
        self.assertEqual(result.note, "Poznámka")
        self.assertEqual(result.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(result.created_by_id, creator.pk)
        self.assertEqual(str(result.sort_date), "1998-01-01")
        self.assertEqual(
            set(result._state.fields_cache),
            {"person", "record_type", "place", "created_by"},
        )

    def test_create_rejects_broad_access_and_rolls_back(self) -> None:
        with self.assertRaises(ValidationError) as context:
            create_health_record(
                data=self.make_data(access_level=AccessLevel.PUBLIC)
            )

        self.assert_error(context, "access_level", "health_access_too_broad")
        self.assertFalse(HealthRecord.objects.exists())

    def test_create_rejects_inactive_type(self) -> None:
        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )
        with self.assertRaises(ValidationError) as context:
            create_health_record(data=self.make_data())

        self.assert_error(
            context,
            "record_type",
            "health_record_type_inactive",
        )

    def test_create_rejects_unsaved_and_missing_foreign_keys(self) -> None:
        missing = Person.objects.create(first_name="Z", last_name="Z")
        Person.objects.filter(pk=missing.pk).delete()
        values = (Person(), missing)
        for person in values:
            with self.subTest(person=person.pk):
                with self.assertRaises(ValidationError) as context:
                    create_health_record(data=self.make_data(person=person))
                self.assert_error(
                    context,
                    "person",
                    "health_person_unsaved",
                )

    def test_create_rejects_unsaved_type_place_and_creator(self) -> None:
        cases = (
            (
                self.make_data(record_type=HealthRecordType()),
                None,
                "record_type",
                "health_record_type_unsaved",
            ),
            (
                self.make_data(place=Place()),
                None,
                "place",
                "health_place_unsaved",
            ),
            (
                self.make_data(),
                get_user_model()(username="unsaved"),
                "created_by",
                "health_created_by_unsaved",
            ),
        )
        for data, created_by, key, code in cases:
            with self.subTest(key=key):
                with self.assertRaises(ValidationError) as context:
                    create_health_record(data=data, created_by=created_by)
                self.assert_error(context, key, code)

    def test_update_applies_full_snapshot_and_preserves_fresh_metadata(self) -> None:
        creator = get_user_model().objects.create_user(username="author")
        fresh_creator = get_user_model().objects.create_user(username="fresh")
        record = create_health_record(
            data=self.make_data(),
            created_by=creator,
        )
        archived_at = timezone.now()
        HealthRecord.objects.filter(pk=record.pk).update(
            created_by=fresh_creator,
            archived_at=archived_at,
            archived_by=fresh_creator,
            archive_reason="Archiv",
            deleted_by=fresh_creator,
            deletion_reason="Ponechat",
        )

        result = update_health_record(
            health_record=record,
            data=self.make_data(
                title="  Změněný  ",
                description="  Popis  ",
                provider_name="  Lékař  ",
                note="  Poznámka  ",
                person=self.other_person,
                record_type=self.other_type,
                place=self.place,
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.VERIFIED,
                date_precision=DatePrecision.RANGE,
                date_qualifier=DateQualifier.APPROXIMATE,
                start_year=2001,
                end_year=2002,
                original_date_text="  2001–2002  ",
                date_note="  odhad  ",
            ),
        )

        self.assertEqual(result.title, "Změněný")
        self.assertEqual(result.description, "Popis")
        self.assertEqual(result.provider_name, "Lékař")
        self.assertEqual(result.note, "Poznámka")
        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.record_type_id, self.other_type.pk)
        self.assertEqual(result.place_id, self.place.pk)
        self.assertEqual(result.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.date_precision, DatePrecision.RANGE)
        self.assertEqual(result.date_qualifier, DateQualifier.APPROXIMATE)
        self.assertEqual(result.start_year, 2001)
        self.assertEqual(result.end_year, 2002)
        self.assertEqual(str(result.sort_date), "2001-01-01")
        self.assertEqual(str(result.sort_date_end), "2002-12-31")
        self.assertEqual(result.original_date_text, "2001–2002")
        self.assertEqual(result.date_note, "odhad")
        self.assertEqual(result.created_by_id, fresh_creator.pk)
        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archived_by_id, fresh_creator.pk)
        self.assertEqual(result.archive_reason, "Archiv")
        self.assertEqual(result.deleted_by_id, fresh_creator.pk)
        self.assertEqual(result.deletion_reason, "Ponechat")

    def test_invalid_update_rolls_back_original_record(self) -> None:
        record = create_health_record(data=self.make_data())
        with self.assertRaises(ValidationError):
            update_health_record(
                health_record=record,
                data=self.make_data(
                    title="",
                    description="",
                    access_level=AccessLevel.PUBLIC,
                ),
            )

        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")
        self.assertEqual(record.access_level, AccessLevel.RESTRICTED)

    def test_update_allows_archived_record_and_same_inactive_type(self) -> None:
        record = create_health_record(data=self.make_data())
        archived_at = timezone.now()
        HealthRecord.objects.filter(pk=record.pk).update(archived_at=archived_at)
        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )

        result = update_health_record(
            health_record=record,
            data=self.make_data(title="Historická změna"),
        )

        self.assertEqual(result.title, "Historická změna")
        self.assertEqual(result.archived_at, archived_at)

    def test_update_rejects_change_to_other_inactive_type(self) -> None:
        record = create_health_record(data=self.make_data())
        self.other_type.is_active = False
        self.other_type.save(update_fields=("is_active",))
        with self.assertRaises(ValidationError) as context:
            update_health_record(
                health_record=record,
                data=self.make_data(record_type=self.other_type),
            )

        self.assert_error(
            context,
            "record_type",
            "health_record_type_inactive",
        )

    def test_update_rejects_soft_deleted_record_without_mutation(self) -> None:
        record = create_health_record(data=self.make_data())
        HealthRecord.objects.filter(pk=record.pk).update(deleted_at=timezone.now())
        with self.assertRaises(ValidationError) as context:
            update_health_record(
                health_record=record,
                data=self.make_data(title="Zakázaná změna"),
            )

        self.assert_error(context, "health_record", "health_record_deleted")
        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")
