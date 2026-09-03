from datetime import date
from importlib import import_module
from inspect import Parameter, signature

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, migrations, models, transaction
from django.test import SimpleTestCase, TestCase

from common.choices import AccessLevel, DatePrecision, VerificationStatus
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from people.models import Person
from places.models import Place

from . import permissions
from .models import HealthRecord, HealthRecordType
from .permissions import can_view_health_record_access


class HealthRecordModelTests(SimpleTestCase):
    def make_record(self, **overrides) -> HealthRecord:
        values = {
            "person": Person(first_name="Jan", last_name="Novák"),
            "record_type": HealthRecordType(code="custom", name="Vlastní"),
            "title": "Vyšetření",
        }
        values.update(overrides)
        return HealthRecord(**values)

    def assert_validation_code(
        self,
        record: HealthRecord,
        field_name: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            record.full_clean(
                exclude=("person", "record_type", "place"),
                validate_constraints=False,
            )
        self.assertIn(
            code,
            {
                error.code
                for error in context.exception.error_dict[field_name]
            },
        )

    def test_model_uses_approved_mixins_in_exact_order(self) -> None:
        self.assertEqual(
            HealthRecord.__bases__,
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

    def test_foreign_keys_have_approved_contract(self) -> None:
        expected = {
            "person": (Person, False, False),
            "record_type": (HealthRecordType, False, False),
            "place": (Place, True, True),
        }
        for field_name, (target, null, blank) in expected.items():
            with self.subTest(field_name=field_name):
                field = HealthRecord._meta.get_field(field_name)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertIs(field.null, null)
                self.assertIs(field.blank, blank)

    def test_default_access_and_verification_are_safe(self) -> None:
        record = self.make_record()

        self.assertEqual(record.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            record.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(record.date_precision, DatePrecision.UNKNOWN)

    def test_partial_date_year_is_derived(self) -> None:
        record = self.make_record(
            date_precision=DatePrecision.YEAR,
            start_year=1998,
        )

        record.full_clean(
            exclude=("person", "record_type", "place"),
            validate_constraints=False,
        )

        self.assertEqual(record.sort_date, date(1998, 1, 1))
        self.assertEqual(record.sort_date_end, date(1998, 12, 31))

    def test_partial_date_and_health_errors_are_aggregated(self) -> None:
        record = self.make_record(
            title="",
            description="",
            access_level=AccessLevel.PUBLIC,
            date_precision=DatePrecision.EXACT,
            start_year=1998,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean(
                exclude=("person", "record_type", "place"),
                validate_constraints=False,
            )

        self.assertEqual(
            {
                field_name: {error.code for error in errors}
                for field_name, errors in context.exception.error_dict.items()
            },
            {
                "start_month": {"missing_month"},
                "start_day": {"missing_day"},
                NON_FIELD_ERRORS: {"health_record_content_required"},
                "access_level": {"health_access_too_broad"},
            },
        )

    def test_text_fields_and_metadata_have_approved_contract(self) -> None:
        for field_name in ("title", "provider_name"):
            with self.subTest(field_name=field_name):
                field = HealthRecord._meta.get_field(field_name)
                self.assertIsInstance(field, models.CharField)
                self.assertEqual(field.max_length, 255)
                self.assertTrue(field.blank)
        for field_name in ("description", "note"):
            with self.subTest(field_name=field_name):
                field = HealthRecord._meta.get_field(field_name)
                self.assertIsInstance(field, models.TextField)
                self.assertTrue(field.blank)
        self.assertEqual(
            HealthRecord._meta.ordering,
            ("person_id", "sort_date", "sort_date_end", "pk"),
        )
        self.assertEqual(
            tuple(
                constraint.name
                for constraint in HealthRecord._meta.constraints
            ),
            ("health_record_access_not_broader_than_restricted",),
        )

    def test_requires_title_or_description(self) -> None:
        self.assert_validation_code(
            self.make_record(title=" \t", description="\n"),
            NON_FIELD_ERRORS,
            "health_record_content_required",
        )

    def test_accepts_description_without_title(self) -> None:
        self.make_record(title="", description="Dlouhodobý stav").full_clean(
            exclude=("person", "record_type", "place"),
            validate_constraints=False,
        )

    def test_rejects_access_broader_than_restricted(self) -> None:
        for access_level in (
            AccessLevel.PUBLIC,
            AccessLevel.AUTHENTICATED,
        ):
            with self.subTest(access_level=access_level):
                self.assert_validation_code(
                    self.make_record(access_level=access_level),
                    "access_level",
                    "health_access_too_broad",
                )

    def test_accepts_restricted_and_admin_only(self) -> None:
        for access_level in (
            AccessLevel.RESTRICTED,
            AccessLevel.ADMIN_ONLY,
        ):
            with self.subTest(access_level=access_level):
                self.make_record(access_level=access_level).full_clean(
                    exclude=("person", "record_type", "place"),
                    validate_constraints=False,
                )

    def test_sensitive_record_remains_fail_closed_in_admin(self) -> None:
        self.assertNotIn(HealthRecord, admin.site._registry)


class HealthRecordDatabaseTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(first_name="Jan", last_name="Novák")
        self.record_type = HealthRecordType.objects.create(
            code="custom",
            name="Vlastní",
        )

    def create_record(self, **overrides) -> HealthRecord:
        values = {
            "person": self.person,
            "record_type": self.record_type,
            "title": "Vyšetření",
        }
        values.update(overrides)
        return HealthRecord.objects.create(**values)

    def test_database_default_is_restricted(self) -> None:
        record = self.create_record()

        self.assertEqual(record.access_level, AccessLevel.RESTRICTED)

    def test_database_constraint_rejects_broader_access(self) -> None:
        for access_level in (
            AccessLevel.PUBLIC,
            AccessLevel.AUTHENTICATED,
        ):
            with self.subTest(access_level=access_level):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.create_record(access_level=access_level)

    def test_database_constraint_accepts_admin_only(self) -> None:
        record = self.create_record(access_level=AccessLevel.ADMIN_ONLY)

        self.assertEqual(record.access_level, AccessLevel.ADMIN_ONLY)


class HealthRecordPermissionApiTests(SimpleTestCase):
    def test_public_api_is_exact_and_keyword_only(self) -> None:
        self.assertEqual(
            permissions.__all__,
            (
                "can_view_health_record_access",
                "get_health_record_visibility_filter",
            ),
        )
        parameters = signature(can_view_health_record_access).parameters
        self.assertEqual(tuple(parameters), ("actor", "access_level"))
        self.assertTrue(
            all(
                parameter.kind is Parameter.KEYWORD_ONLY
                for parameter in parameters.values()
            )
        )


class HealthRecordPermissionTests(TestCase):
    def create_user(self, username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    def grant(self, actor, codename: str) -> None:
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                content_type__model="user",
                codename=codename,
            )
        )

    def test_policy_delegates_restricted_and_admin_only_to_general_access(self) -> None:
        restricted = self.create_user("restricted")
        self.grant(restricted, "view_restricted_content")
        admin = self.create_user("admin")
        self.grant(admin, "view_admin_only_content")
        ordinary = self.create_user("ordinary")
        staff = self.create_user("staff", is_staff=True)
        superuser = self.create_user("superuser", is_superuser=True)
        inactive = self.create_user("inactive", is_active=False)
        self.grant(inactive, "view_restricted_content")

        expectations = (
            (AnonymousUser(), AccessLevel.RESTRICTED, False),
            (ordinary, AccessLevel.RESTRICTED, False),
            (staff, AccessLevel.RESTRICTED, False),
            (restricted, AccessLevel.RESTRICTED, True),
            (restricted, AccessLevel.ADMIN_ONLY, False),
            (admin, AccessLevel.ADMIN_ONLY, True),
            (superuser, AccessLevel.RESTRICTED, True),
            (superuser, AccessLevel.ADMIN_ONLY, True),
            (inactive, AccessLevel.RESTRICTED, False),
        )
        for actor, access_level, expected in expectations:
            with self.subTest(
                actor=getattr(actor, "username", "anonymous"),
                access_level=access_level,
            ):
                self.assertIs(
                    can_view_health_record_access(
                        actor=actor,
                        access_level=access_level,
                    ),
                    expected,
                )

    def test_policy_rejects_broader_health_levels(self) -> None:
        for access_level in (
            AccessLevel.PUBLIC,
            AccessLevel.AUTHENTICATED,
        ):
            with self.subTest(access_level=access_level):
                with self.assertRaises(ValidationError) as context:
                    can_view_health_record_access(
                        actor=AnonymousUser(),
                        access_level=access_level,
                    )
                self.assertEqual(
                    context.exception.error_dict["access_level"][0].code,
                    "health_access_too_broad",
                )

    def test_policy_preserves_general_actor_validation(self) -> None:
        with self.assertRaises(ValidationError) as context:
            can_view_health_record_access(
                actor=None,
                access_level=AccessLevel.RESTRICTED,
            )

        self.assertEqual(
            context.exception.error_dict["actor"][0].code,
            "actor_invalid",
        )


class HealthRecordMigrationTests(SimpleTestCase):
    migration = import_module("health.migrations.0002_health_records")

    def test_migration_has_exact_dependencies_and_single_model(self) -> None:
        self.assertEqual(
            self.migration.Migration.dependencies,
            [
                ("health", "0001_health_record_types"),
                ("people", "0010_person_titles_biography"),
                ("places", "0009_persongravesite"),
                ("accounts", "__first__"),
            ],
        )
        self.assertEqual(len(self.migration.Migration.operations), 1)
        operation = self.migration.Migration.operations[0]
        self.assertIsInstance(operation, migrations.CreateModel)
        self.assertEqual(operation.name, "HealthRecord")
