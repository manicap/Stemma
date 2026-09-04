from dataclasses import FrozenInstanceError, fields, replace
from inspect import Parameter, signature
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
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
from .permissions import get_health_record_visibility_filter
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
            ("data", "actor"),
        )
        self.assertEqual(
            tuple(signature(update_health_record).parameters),
            ("health_record", "data", "actor"),
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
        self.actor = self.writer("writer")

    def writer(self, username: str, **values):
        return self.user_with_permissions(
            username,
            "health.add_healthrecord",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
            "accounts.view_admin_only_content",
            **values,
        )

    def user_with_permissions(
        self,
        username: str,
        *permission_keys: str,
        **values,
    ):
        actor = get_user_model().objects.create_user(
            username=username,
            **values,
        )
        for permission_key in permission_keys:
            app_label, codename = permission_key.split(".", 1)
            actor.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label,
                    codename=codename,
                )
            )
        return actor

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
        creator = self.writer("creator")
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
            actor=creator,
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
                data=self.make_data(access_level=AccessLevel.PUBLIC),
                actor=self.actor,
            )

        self.assert_error(context, "access_level", "health_access_too_broad")
        self.assertFalse(HealthRecord.objects.exists())

    def test_create_rejects_inactive_type(self) -> None:
        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )
        with self.assertRaises(ValidationError) as context:
            create_health_record(data=self.make_data(), actor=self.actor)

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
                    create_health_record(
                        data=self.make_data(person=person),
                        actor=self.actor,
                    )
                self.assert_error(
                    context,
                    "person",
                    "health_person_unsaved",
                )

    def test_create_rejects_unsaved_type_and_place(self) -> None:
        cases = (
            (
                self.make_data(record_type=HealthRecordType()),
                "record_type",
                "health_record_type_unsaved",
            ),
            (
                self.make_data(place=Place()),
                "place",
                "health_place_unsaved",
            ),
        )
        for data, key, code in cases:
            with self.subTest(key=key):
                with self.assertRaises(ValidationError) as context:
                    create_health_record(data=data, actor=self.actor)
                self.assert_error(context, key, code)

    def test_update_applies_full_snapshot_and_preserves_fresh_metadata(self) -> None:
        creator = self.writer("author")
        fresh_creator = get_user_model().objects.create_user(username="fresh")
        record = create_health_record(
            data=self.make_data(),
            actor=creator,
        )
        HealthRecord.objects.filter(pk=record.pk).update(
            created_by=fresh_creator,
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
            actor=self.actor,
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
        self.assertIsNone(result.archived_at)
        self.assertIsNone(result.deleted_at)
        self.assertEqual(result.archived_by_id, fresh_creator.pk)
        self.assertEqual(result.archive_reason, "Archiv")
        self.assertEqual(result.deleted_by_id, fresh_creator.pk)
        self.assertEqual(result.deletion_reason, "Ponechat")

    def test_invalid_update_rolls_back_original_record(self) -> None:
        record = create_health_record(data=self.make_data(), actor=self.actor)
        with self.assertRaises(ValidationError):
            update_health_record(
                health_record=record,
                data=self.make_data(
                    title="",
                    description="",
                    access_level=AccessLevel.PUBLIC,
                ),
                actor=self.actor,
            )

        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")
        self.assertEqual(HealthRecord.objects.count(), 1)
        self.assertEqual(record.access_level, AccessLevel.RESTRICTED)

    def test_actor_must_be_current_active_and_have_model_permission(
        self,
    ) -> None:
        record = create_health_record(data=self.make_data(), actor=self.actor)
        view_only = self.user_with_permissions(
            "view-only",
            "accounts.view_restricted_content",
        )
        inactive = self.writer("inactive", is_active=False)
        missing = self.writer("missing")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        forged = SimpleNamespace(
            is_authenticated=True,
            pk=self.actor.pk,
        )
        for actor in (AnonymousUser(), view_only, inactive, missing, forged):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    create_health_record(data=self.make_data(), actor=actor)
                with self.assertRaises(PermissionDenied):
                    update_health_record(
                        health_record=record,
                        data=self.make_data(title="Zakázáno"),
                        actor=actor,
                    )

        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")

    def test_actor_authorization_precedes_update_target_validation(self) -> None:
        unsaved = HealthRecord()
        with self.assertRaises(PermissionDenied):
            update_health_record(
                health_record=unsaved,
                data=self.make_data(),
                actor=AnonymousUser(),
            )

        with self.assertRaises(ValidationError) as context:
            update_health_record(
                health_record=unsaved,
                data=self.make_data(),
                actor=self.actor,
            )
        self.assert_error(
            context,
            "health_record",
            "health_record_unsaved",
        )

    def test_fresh_permission_revocation_is_enforced(self) -> None:
        actor = self.writer("revoked")
        record = create_health_record(data=self.make_data(), actor=actor)
        actor.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="health",
                codename="change_healthrecord",
            )
        )

        with self.assertRaises(PermissionDenied):
            update_health_record(
                health_record=record,
                data=self.make_data(title="Zakázáno"),
                actor=actor,
            )

        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")

    def test_model_permission_does_not_bypass_content_access(self) -> None:
        add_only = self.user_with_permissions(
            "add-only",
            "health.add_healthrecord",
        )
        restricted_writer = self.user_with_permissions(
            "restricted-writer",
            "health.add_healthrecord",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
        )
        with self.assertRaises(PermissionDenied):
            create_health_record(data=self.make_data(), actor=add_only)
        with self.assertRaises(PermissionDenied):
            create_health_record(
                data=self.make_data(access_level=AccessLevel.ADMIN_ONLY),
                actor=restricted_writer,
            )

        record = create_health_record(data=self.make_data(), actor=self.actor)
        with self.assertRaises(PermissionDenied):
            update_health_record(
                health_record=record,
                data=self.make_data(access_level=AccessLevel.ADMIN_ONLY),
                actor=restricted_writer,
            )
        record.refresh_from_db()
        self.assertEqual(record.access_level, AccessLevel.RESTRICTED)

    def test_person_access_and_lifecycle_are_rechecked_from_database(
        self,
    ) -> None:
        restricted_writer = self.user_with_permissions(
            "person-writer",
            "health.add_healthrecord",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
        )
        hidden = Person.objects.create(first_name="Skrytá")
        archived = Person.objects.create(first_name="Archivovaná")
        deleted = Person.objects.create(first_name="Odstraněná")
        Person.objects.filter(pk=hidden.pk).update(
            access_level=AccessLevel.ADMIN_ONLY
        )
        Person.objects.filter(pk=archived.pk).update(archived_at=timezone.now())
        Person.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())
        for person, actor in (
            (hidden, restricted_writer),
            (archived, self.actor),
            (deleted, self.actor),
        ):
            with self.subTest(person=person.pk):
                with self.assertRaises(Person.DoesNotExist):
                    create_health_record(
                        data=self.make_data(person=person),
                        actor=actor,
                    )

        record = create_health_record(data=self.make_data(), actor=self.actor)
        for person, actor in (
            (hidden, restricted_writer),
            (archived, self.actor),
            (deleted, self.actor),
        ):
            with self.subTest(update_person=person.pk):
                with self.assertRaises(Person.DoesNotExist):
                    update_health_record(
                        health_record=record,
                        data=self.make_data(person=person),
                        actor=actor,
                    )
        record.refresh_from_db()
        self.assertEqual(record.person_id, self.person.pk)

    def test_saved_but_deleted_type_and_place_are_rejected_from_database(
        self,
    ) -> None:
        stale_type = HealthRecordType.objects.create(
            code="stale",
            name="Stale",
        )
        stale_type_pk = stale_type.pk
        stale_type.delete()
        stale_type.pk = stale_type_pk
        stale_place = Place.objects.create(
            name="Stale",
            normalized_name="stale",
        )
        stale_place_pk = stale_place.pk
        stale_place.delete()
        stale_place.pk = stale_place_pk

        for data, key, code in (
            (
                self.make_data(record_type=stale_type),
                "record_type",
                "health_record_type_unsaved",
            ),
            (
                self.make_data(place=stale_place),
                "place",
                "health_place_unsaved",
            ),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError) as context:
                    create_health_record(data=data, actor=self.actor)
                self.assert_error(context, key, code)

    def test_update_uses_central_health_visibility_for_current_target(
        self,
    ) -> None:
        record = create_health_record(data=self.make_data(), actor=self.actor)
        with patch(
            "health.services.get_health_record_visibility_filter",
            wraps=get_health_record_visibility_filter,
        ) as policy:
            result = update_health_record(
                health_record=record,
                data=self.make_data(title="Změna"),
                actor=self.actor,
            )

        self.assertEqual(result.title, "Změna")
        self.assertEqual(policy.call_count, 1)

    def test_hidden_and_missing_current_targets_are_indistinguishable(
        self,
    ) -> None:
        restricted_writer = self.user_with_permissions(
            "target-writer",
            "health.change_healthrecord",
            "accounts.view_restricted_content",
        )
        hidden = create_health_record(
            data=self.make_data(access_level=AccessLevel.ADMIN_ONLY),
            actor=self.actor,
        )
        missing = create_health_record(data=self.make_data(), actor=self.actor)
        missing_pk = missing.pk
        HealthRecord.objects.filter(pk=missing_pk).delete()
        missing.pk = missing_pk

        for record in (hidden, missing):
            with self.subTest(record=record.pk):
                with self.assertRaises(HealthRecord.DoesNotExist):
                    update_health_record(
                        health_record=record,
                        data=self.make_data(),
                        actor=restricted_writer,
                    )

    def test_update_rejects_archived_record_and_inactive_current_type(
        self,
    ) -> None:
        archived_record = create_health_record(
            data=self.make_data(),
            actor=self.actor,
        )
        archived_at = timezone.now()
        HealthRecord.objects.filter(pk=archived_record.pk).update(
            archived_at=archived_at
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            update_health_record(
                health_record=archived_record,
                data=self.make_data(title="Zakázaná změna"),
                actor=self.actor,
            )

        inactive_type_record = create_health_record(
            data=self.make_data(),
            actor=self.actor,
        )
        HealthRecordType.objects.filter(pk=self.record_type.pk).update(
            is_active=False
        )
        with self.assertRaises(HealthRecord.DoesNotExist):
            update_health_record(
                health_record=inactive_type_record,
                data=self.make_data(record_type=self.other_type),
                actor=self.actor,
            )

    def test_update_rejects_change_to_other_inactive_type(self) -> None:
        record = create_health_record(data=self.make_data(), actor=self.actor)
        self.other_type.is_active = False
        self.other_type.save(update_fields=("is_active",))
        with self.assertRaises(ValidationError) as context:
            update_health_record(
                health_record=record,
                data=self.make_data(record_type=self.other_type),
                actor=self.actor,
            )

        self.assert_error(
            context,
            "record_type",
            "health_record_type_inactive",
        )

    def test_update_rejects_soft_deleted_record_without_mutation(self) -> None:
        record = create_health_record(data=self.make_data(), actor=self.actor)
        HealthRecord.objects.filter(pk=record.pk).update(deleted_at=timezone.now())
        with self.assertRaises(HealthRecord.DoesNotExist):
            update_health_record(
                health_record=record,
                data=self.make_data(title="Zakázaná změna"),
                actor=self.actor,
            )
        record.refresh_from_db()
        self.assertEqual(record.title, "Kontrola")
