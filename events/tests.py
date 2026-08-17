from datetime import date
from importlib import import_module
from inspect import getsource

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, migrations, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.choices import AccessLevel, DatePrecision, DateQualifier
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from people.models import Person
from places.models import Place

from .apps import EventsConfig
from .models import (
    AllowedEventRole,
    Event,
    EventParticipant,
    EventType,
    ParticipantRole,
)


EXPECTED_EVENT_TYPES = (
    {
        "code": "birth",
        "name": "Narození",
        "description": "Narození osoby.",
        "sort_order": 10,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "baptism",
        "name": "Křest",
        "description": "Křest osoby.",
        "sort_order": 20,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "marriage",
        "name": "Sňatek",
        "description": "Uzavření manželství.",
        "sort_order": 30,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "divorce",
        "name": "Rozvod",
        "description": "Ukončení manželství rozvodem.",
        "sort_order": 40,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "relocation",
        "name": "Stěhování",
        "description": "Přestěhování osoby nebo domácnosti.",
        "sort_order": 50,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "education",
        "name": "Studium",
        "description": (
            "Studium na škole nebo v jiném vzdělávacím programu."
        ),
        "sort_order": 60,
        "is_active": True,
        "is_system": True,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "graduation",
        "name": "Maturita",
        "description": (
            "Složení maturity nebo obdobné závěrečné zkoušky."
        ),
        "sort_order": 70,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "military_service",
        "name": "Vojenská služba",
        "description": "Výkon vojenské služby.",
        "sort_order": 80,
        "is_active": True,
        "is_system": True,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "employment",
        "name": "Zaměstnání",
        "description": "Pracovní nebo profesní působení.",
        "sort_order": 90,
        "is_active": True,
        "is_system": True,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "death",
        "name": "Úmrtí",
        "description": "Úmrtí osoby.",
        "sort_order": 100,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": True,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "funeral",
        "name": "Pohřeb",
        "description": "Pohřeb nebo jiné rozloučení se zemřelým.",
        "sort_order": 110,
        "is_active": True,
        "is_system": True,
        "supports_date_range": False,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
    {
        "code": "other",
        "name": "Jiná událost",
        "description": "Jiná životní událost.",
        "sort_order": 120,
        "is_active": True,
        "is_system": True,
        "supports_date_range": True,
        "allows_place": True,
        "default_show_in_overview": False,
        "default_access_level": AccessLevel.PUBLIC,
    },
)
EXPECTED_EVENT_TYPE_CODES = tuple(
    event_type["code"] for event_type in EXPECTED_EVENT_TYPES
)
EXPECTED_PARTICIPANT_ROLES = (
    {
        "code": "subject",
        "name": "Hlavní osoba",
        "description": "Osoba, které se událost primárně týká.",
        "sort_order": 10,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "born_person",
        "name": "Narozená osoba",
        "description": "Osoba, jejíž narození událost eviduje.",
        "sort_order": 20,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "baptized_person",
        "name": "Křtěná osoba",
        "description": "Osoba, jejíž křest událost eviduje.",
        "sort_order": 30,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "deceased_person",
        "name": "Zemřelá osoba",
        "description": (
            "Osoba, jejíž úmrtí nebo pohřeb událost eviduje."
        ),
        "sort_order": 40,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "spouse",
        "name": "Manželský partner",
        "description": "Partner při sňatku nebo rozvodu.",
        "sort_order": 50,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "parent",
        "name": "Rodič",
        "description": "Rodič hlavní osoby nebo jiného účastníka.",
        "sort_order": 60,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "child",
        "name": "Dítě",
        "description": "Dítě hlavní osoby nebo jiného účastníka.",
        "sort_order": 70,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "godparent",
        "name": "Kmotr nebo kmotra",
        "description": "Kmotr nebo kmotra při křtu.",
        "sort_order": 80,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "witness",
        "name": "Svědek",
        "description": "Svědek události.",
        "sort_order": 90,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "participant",
        "name": "Účastník",
        "description": "Další osoba přímo účastná události.",
        "sort_order": 100,
        "is_active": True,
        "is_system": True,
    },
    {
        "code": "other",
        "name": "Jiná role",
        "description": "Jiná role osoby v události.",
        "sort_order": 110,
        "is_active": True,
        "is_system": True,
    },
)
EXPECTED_PARTICIPANT_ROLE_CODES = tuple(
    role["code"] for role in EXPECTED_PARTICIPANT_ROLES
)
EXPECTED_ALLOWED_EVENT_ROLES = (
    ("birth", "born_person", 1, 1, 10),
    ("birth", "parent", 0, 2, 20),
    ("birth", "witness", 0, None, 30),
    ("birth", "participant", 0, None, 80),
    ("birth", "other", 0, None, 90),
    ("baptism", "baptized_person", 1, 1, 10),
    ("baptism", "parent", 0, 2, 20),
    ("baptism", "godparent", 0, None, 30),
    ("baptism", "witness", 0, None, 40),
    ("baptism", "participant", 0, None, 80),
    ("baptism", "other", 0, None, 90),
    ("marriage", "spouse", 2, 2, 10),
    ("marriage", "parent", 0, None, 20),
    ("marriage", "witness", 0, None, 30),
    ("marriage", "participant", 0, None, 80),
    ("marriage", "other", 0, None, 90),
    ("divorce", "spouse", 1, 2, 10),
    ("divorce", "witness", 0, None, 30),
    ("divorce", "participant", 0, None, 80),
    ("divorce", "other", 0, None, 90),
    ("relocation", "subject", 1, None, 10),
    ("relocation", "participant", 0, None, 80),
    ("relocation", "other", 0, None, 90),
    ("education", "subject", 1, 1, 10),
    ("education", "participant", 0, None, 80),
    ("education", "other", 0, None, 90),
    ("graduation", "subject", 1, 1, 10),
    ("graduation", "witness", 0, None, 30),
    ("graduation", "participant", 0, None, 80),
    ("graduation", "other", 0, None, 90),
    ("military_service", "subject", 1, 1, 10),
    ("military_service", "participant", 0, None, 80),
    ("military_service", "other", 0, None, 90),
    ("employment", "subject", 1, 1, 10),
    ("employment", "participant", 0, None, 80),
    ("employment", "other", 0, None, 90),
    ("death", "deceased_person", 1, 1, 10),
    ("death", "witness", 0, None, 30),
    ("death", "participant", 0, None, 80),
    ("death", "other", 0, None, 90),
    ("funeral", "deceased_person", 1, 1, 10),
    ("funeral", "witness", 0, None, 30),
    ("funeral", "participant", 0, None, 80),
    ("funeral", "other", 0, None, 90),
    ("other", "subject", 1, None, 10),
    ("other", "parent", 0, None, 20),
    ("other", "child", 0, None, 30),
    ("other", "spouse", 0, None, 40),
    ("other", "godparent", 0, None, 50),
    ("other", "witness", 0, None, 60),
    ("other", "participant", 0, None, 80),
    ("other", "other", 0, None, 90),
)


class EventsApplicationTests(SimpleTestCase):
    """Ověření konfigurace a registrace aplikace events."""

    def test_app_config_exists_and_is_registered(self) -> None:
        app_config = apps.get_app_config("events")

        self.assertIsInstance(app_config, EventsConfig)
        self.assertEqual(app_config.name, "events")
        self.assertEqual(app_config.label, "events")
        self.assertIn("events.apps.EventsConfig", settings.INSTALLED_APPS)
        self.assertIs(apps.get_model("events", "EventType"), EventType)


class EventTypeModelTests(SimpleTestCase):
    """Ověření struktury a metadat typů událostí."""

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(EventType._meta.abstract)
        self.assertEqual(EventType.__bases__, (LookupModel,))

    def test_model_has_only_expected_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in EventType._meta.local_fields),
            (
                "id",
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
                "supports_date_range",
                "allows_place",
                "default_show_in_overview",
                "default_access_level",
            ),
        )

    def test_inherited_field_types_and_options(self) -> None:
        expected_types = {
            "id": models.BigAutoField,
            "code": models.CharField,
            "name": models.CharField,
            "description": models.TextField,
            "sort_order": models.PositiveIntegerField,
            "is_active": models.BooleanField,
            "is_system": models.BooleanField,
        }

        for field_name, expected_type in expected_types.items():
            with self.subTest(field_name=field_name):
                self.assertIsInstance(
                    EventType._meta.get_field(field_name),
                    expected_type,
                )

        code = EventType._meta.get_field("code")
        name = EventType._meta.get_field("name")
        description = EventType._meta.get_field("description")
        sort_order = EventType._meta.get_field("sort_order")
        is_active = EventType._meta.get_field("is_active")
        is_system = EventType._meta.get_field("is_system")

        self.assertEqual(code.max_length, 50)
        self.assertTrue(code.unique)
        self.assertFalse(code.null)
        self.assertFalse(code.blank)
        self.assertEqual(name.max_length, 100)
        self.assertFalse(name.null)
        self.assertFalse(name.blank)
        self.assertFalse(description.null)
        self.assertTrue(description.blank)
        self.assertEqual(sort_order.default, 0)
        self.assertIs(is_active.default, True)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_configuration_field_types(self) -> None:
        for field_name in (
            "supports_date_range",
            "allows_place",
            "default_show_in_overview",
        ):
            with self.subTest(field_name=field_name):
                self.assertIsInstance(
                    EventType._meta.get_field(field_name),
                    models.BooleanField,
                )

        self.assertIsInstance(
            EventType._meta.get_field("default_access_level"),
            models.CharField,
        )

    def test_configuration_field_options_and_defaults(self) -> None:
        supports_date_range = EventType._meta.get_field(
            "supports_date_range"
        )
        allows_place = EventType._meta.get_field("allows_place")
        show_in_overview = EventType._meta.get_field(
            "default_show_in_overview"
        )
        access_level = EventType._meta.get_field(
            "default_access_level"
        )

        for field in (
            supports_date_range,
            allows_place,
            show_in_overview,
            access_level,
        ):
            with self.subTest(field_name=field.name):
                self.assertFalse(field.null)
                self.assertFalse(field.blank)

        self.assertIs(supports_date_range.default, False)
        self.assertIs(allows_place.default, True)
        self.assertIs(show_in_overview.default, False)
        self.assertEqual(access_level.max_length, 20)
        self.assertEqual(access_level.choices, AccessLevel.choices)
        self.assertEqual(access_level.default, AccessLevel.PUBLIC)

    def test_model_defaults(self) -> None:
        event_type = EventType(code="test", name="Testovací typ")

        self.assertEqual(event_type.description, "")
        self.assertEqual(event_type.sort_order, 0)
        self.assertTrue(event_type.is_active)
        self.assertFalse(event_type.is_system)
        self.assertFalse(event_type.supports_date_range)
        self.assertTrue(event_type.allows_place)
        self.assertFalse(event_type.default_show_in_overview)
        self.assertEqual(
            event_type.default_access_level,
            AccessLevel.PUBLIC,
        )

    def test_model_metadata_and_string_representation(self) -> None:
        event_type = EventType(code="test", name="Testovací typ")

        self.assertEqual(
            EventType._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(EventType._meta.verbose_name, "Typ události")
        self.assertEqual(
            EventType._meta.verbose_name_plural,
            "Typy událostí",
        )
        self.assertEqual(str(event_type), "Testovací typ")


class EventTypeDatabaseTests(TestCase):
    """Ověření databázové integrity typů událostí."""

    def test_duplicate_code_is_rejected(self) -> None:
        EventType.objects.create(code="duplicate", name="První")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventType.objects.create(
                    code="duplicate",
                    name="Druhý",
                )

    def test_name_does_not_have_to_be_unique(self) -> None:
        EventType.objects.create(code="first", name="Stejný název")
        EventType.objects.create(code="second", name="Stejný název")

        self.assertEqual(
            EventType.objects.filter(name="Stejný název").count(),
            2,
        )


class EventTypeDataMigrationTests(TestCase):
    """Ověření základních dat a vratnosti datové migrace."""

    migration = import_module(
        "events.migrations.0002_initial_event_types"
    )
    allowed_roles_migration = import_module(
        "events.migrations.0005_initial_allowed_event_roles"
    )

    def test_initial_event_types_have_exact_values(self) -> None:
        event_types = list(
            EventType.objects.order_by("sort_order").values(
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
                "supports_date_range",
                "allows_place",
                "default_show_in_overview",
                "default_access_level",
            )
        )

        self.assertEqual(event_types, list(EXPECTED_EVENT_TYPES))

    def test_forward_migration_is_idempotent(self) -> None:
        EventType.objects.filter(code="birth").update(
            name="Dočasně změněný název",
            supports_date_range=True,
            default_show_in_overview=False,
        )

        self.migration.create_initial_event_types(apps, None)
        self.migration.create_initial_event_types(apps, None)

        self.assertEqual(EventType.objects.count(), 12)
        birth = EventType.objects.get(code="birth")
        self.assertEqual(birth.name, "Narození")
        self.assertFalse(birth.supports_date_range)
        self.assertTrue(birth.default_show_in_overview)

    def test_reverse_migration_removes_only_initial_types(self) -> None:
        custom_type = EventType.objects.create(
            code="custom",
            name="Vlastní typ",
        )
        self.allowed_roles_migration.remove_initial_allowed_event_roles(
            apps,
            None,
        )

        self.migration.remove_initial_event_types(apps, None)

        self.assertFalse(
            EventType.objects.filter(
                code__in=EXPECTED_EVENT_TYPE_CODES
            ).exists()
        )
        self.assertTrue(
            EventType.objects.filter(pk=custom_type.pk).exists()
        )


class EventTypeAdminTests(SimpleTestCase):
    """Ověření registrace typů událostí v Django Adminu."""

    def test_model_is_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(EventType))


class ParticipantRoleModelTests(SimpleTestCase):
    """Ověření struktury a metadat rolí účastníků."""

    def test_model_is_concrete_direct_lookup_model_subclass(self) -> None:
        self.assertFalse(ParticipantRole._meta.abstract)
        self.assertEqual(ParticipantRole.__bases__, (LookupModel,))

    def test_model_has_only_expected_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in ParticipantRole._meta.local_fields),
            (
                "id",
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
            ),
        )

    def test_field_types_and_options(self) -> None:
        expected_types = {
            "id": models.BigAutoField,
            "code": models.CharField,
            "name": models.CharField,
            "description": models.TextField,
            "sort_order": models.PositiveIntegerField,
            "is_active": models.BooleanField,
            "is_system": models.BooleanField,
        }

        for field_name, expected_type in expected_types.items():
            with self.subTest(field_name=field_name):
                self.assertIsInstance(
                    ParticipantRole._meta.get_field(field_name),
                    expected_type,
                )

        code = ParticipantRole._meta.get_field("code")
        name = ParticipantRole._meta.get_field("name")
        description = ParticipantRole._meta.get_field("description")
        sort_order = ParticipantRole._meta.get_field("sort_order")
        is_active = ParticipantRole._meta.get_field("is_active")
        is_system = ParticipantRole._meta.get_field("is_system")

        self.assertEqual(code.max_length, 50)
        self.assertTrue(code.unique)
        self.assertEqual(name.max_length, 100)
        self.assertTrue(description.blank)
        self.assertFalse(description.null)
        self.assertEqual(sort_order.default, 0)
        self.assertIs(is_active.default, True)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_metadata_and_string_representation(self) -> None:
        role = ParticipantRole(code="test", name="Testovací role")

        self.assertEqual(
            ParticipantRole._meta.ordering,
            ("sort_order", "name", "code"),
        )
        self.assertEqual(
            ParticipantRole._meta.verbose_name,
            "Role účastníka",
        )
        self.assertEqual(
            ParticipantRole._meta.verbose_name_plural,
            "Role účastníků",
        )
        self.assertEqual(str(role), "Testovací role")


class ParticipantRoleDatabaseTests(TestCase):
    """Ověření databázové integrity rolí účastníků."""

    def test_duplicate_code_is_rejected(self) -> None:
        ParticipantRole.objects.create(code="duplicate", name="První")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParticipantRole.objects.create(
                    code="duplicate",
                    name="Druhá",
                )

    def test_name_does_not_have_to_be_unique(self) -> None:
        ParticipantRole.objects.create(code="first", name="Stejný název")
        ParticipantRole.objects.create(code="second", name="Stejný název")

        self.assertEqual(
            ParticipantRole.objects.filter(name="Stejný název").count(),
            2,
        )


class AllowedEventRoleModelTests(SimpleTestCase):
    """Ověření struktury konfigurace povolených rolí."""

    def test_model_is_concrete_direct_model_subclass(self) -> None:
        self.assertFalse(AllowedEventRole._meta.abstract)
        self.assertEqual(AllowedEventRole.__bases__, (models.Model,))

    def test_model_has_only_expected_fields(self) -> None:
        self.assertEqual(
            tuple(field.name for field in AllowedEventRole._meta.local_fields),
            (
                "id",
                "event_type",
                "participant_role",
                "min_count",
                "max_count",
                "sort_order",
                "is_active",
                "is_system",
            ),
        )

    def test_foreign_key_options(self) -> None:
        event_type = AllowedEventRole._meta.get_field("event_type")
        participant_role = AllowedEventRole._meta.get_field(
            "participant_role"
        )

        for field in (event_type, participant_role):
            with self.subTest(field_name=field.name):
                self.assertIsInstance(field, models.ForeignKey)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertFalse(field.null)
                self.assertFalse(field.blank)

        self.assertIs(event_type.remote_field.model, EventType)
        self.assertEqual(event_type.remote_field.related_name, "allowed_roles")
        self.assertIs(participant_role.remote_field.model, ParticipantRole)
        self.assertEqual(
            participant_role.remote_field.related_name,
            "event_type_rules",
        )

    def test_configuration_field_types_and_options(self) -> None:
        min_count = AllowedEventRole._meta.get_field("min_count")
        max_count = AllowedEventRole._meta.get_field("max_count")
        sort_order = AllowedEventRole._meta.get_field("sort_order")
        is_active = AllowedEventRole._meta.get_field("is_active")
        is_system = AllowedEventRole._meta.get_field("is_system")

        self.assertIsInstance(min_count, models.PositiveSmallIntegerField)
        self.assertEqual(min_count.default, 0)
        self.assertFalse(min_count.null)
        self.assertFalse(min_count.blank)
        self.assertIsInstance(max_count, models.PositiveSmallIntegerField)
        self.assertTrue(max_count.null)
        self.assertTrue(max_count.blank)
        self.assertIsInstance(sort_order, models.PositiveIntegerField)
        self.assertEqual(sort_order.default, 0)
        self.assertIsInstance(is_active, models.BooleanField)
        self.assertIs(is_active.default, True)
        self.assertIsInstance(is_system, models.BooleanField)
        self.assertIs(is_system.default, False)
        self.assertFalse(is_system.editable)

    def test_metadata_constraints_and_string_representation(self) -> None:
        constraints = {
            constraint.name: constraint
            for constraint in AllowedEventRole._meta.constraints
        }
        event_type = EventType(code="test", name="Testovací událost")
        role = ParticipantRole(code="test", name="Testovací role")
        rule = AllowedEventRole(
            event_type=event_type,
            participant_role=role,
        )

        self.assertEqual(
            AllowedEventRole._meta.ordering,
            (
                "event_type__sort_order",
                "sort_order",
                "participant_role__sort_order",
                "participant_role__code",
            ),
        )
        self.assertEqual(
            AllowedEventRole._meta.verbose_name,
            "Povolená role události",
        )
        self.assertEqual(
            AllowedEventRole._meta.verbose_name_plural,
            "Povolené role událostí",
        )
        self.assertEqual(
            set(constraints),
            {
                "events_unique_allowed_role",
                "events_valid_allowed_role_counts",
            },
        )
        unique_constraint = constraints["events_unique_allowed_role"]
        count_constraint = constraints["events_valid_allowed_role_counts"]
        self.assertIsInstance(unique_constraint, models.UniqueConstraint)
        self.assertEqual(
            unique_constraint.fields,
            ("event_type", "participant_role"),
        )
        self.assertIsInstance(count_constraint, models.CheckConstraint)
        self.assertEqual(str(rule), "Testovací událost – Testovací role")


class AllowedEventRoleDatabaseTests(TestCase):
    """Ověření databázových omezení povolených rolí."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.first_type = EventType.objects.create(
            code="test_first",
            name="První testovací typ",
        )
        cls.second_type = EventType.objects.create(
            code="test_second",
            name="Druhý testovací typ",
        )
        cls.first_role = ParticipantRole.objects.create(
            code="test_first",
            name="První testovací role",
        )
        cls.second_role = ParticipantRole.objects.create(
            code="test_second",
            name="Druhá testovací role",
        )

    def test_duplicate_event_type_and_role_pair_is_rejected(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AllowedEventRole.objects.create(
                    event_type=self.first_type,
                    participant_role=self.first_role,
                )

    def test_role_can_be_used_by_multiple_event_types(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
        )
        AllowedEventRole.objects.create(
            event_type=self.second_type,
            participant_role=self.first_role,
        )

        self.assertEqual(
            AllowedEventRole.objects.filter(
                participant_role=self.first_role
            ).count(),
            2,
        )

    def test_event_type_can_allow_multiple_roles(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
        )
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.second_role,
        )

        self.assertEqual(
            AllowedEventRole.objects.filter(
                event_type=self.first_type
            ).count(),
            2,
        )

    def test_null_maximum_is_allowed(self) -> None:
        rule = AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
            min_count=2,
            max_count=None,
        )

        self.assertIsNone(rule.max_count)

    def test_maximum_equal_to_minimum_is_allowed(self) -> None:
        rule = AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
            min_count=2,
            max_count=2,
        )

        self.assertEqual(rule.max_count, 2)

    def test_maximum_higher_than_minimum_is_allowed(self) -> None:
        rule = AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
            min_count=1,
            max_count=2,
        )

        self.assertEqual(rule.max_count, 2)

    def test_maximum_lower_than_minimum_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AllowedEventRole.objects.create(
                    event_type=self.first_type,
                    participant_role=self.first_role,
                    min_count=2,
                    max_count=1,
                )

    def test_used_event_type_is_protected_from_deletion(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
        )

        with self.assertRaises(ProtectedError):
            self.first_type.delete()

    def test_used_participant_role_is_protected_from_deletion(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.first_type,
            participant_role=self.first_role,
        )

        with self.assertRaises(ProtectedError):
            self.first_role.delete()


class ParticipantRoleDataMigrationTests(TestCase):
    """Ověření systémových rolí a vratnosti jejich datové migrace."""

    migration = import_module(
        "events.migrations.0004_initial_participant_roles"
    )
    allowed_roles_migration = import_module(
        "events.migrations.0005_initial_allowed_event_roles"
    )

    def test_initial_participant_roles_have_exact_values(self) -> None:
        roles = list(
            ParticipantRole.objects.order_by("sort_order").values(
                "code",
                "name",
                "description",
                "sort_order",
                "is_active",
                "is_system",
            )
        )

        self.assertEqual(roles, list(EXPECTED_PARTICIPANT_ROLES))

    def test_forward_migration_is_idempotent(self) -> None:
        ParticipantRole.objects.filter(code="subject").update(
            name="Dočasně změněný název",
            is_active=False,
            is_system=False,
        )

        self.migration.create_initial_participant_roles(apps, None)
        self.migration.create_initial_participant_roles(apps, None)

        self.assertEqual(ParticipantRole.objects.count(), 11)
        subject = ParticipantRole.objects.get(code="subject")
        self.assertEqual(subject.name, "Hlavní osoba")
        self.assertTrue(subject.is_active)
        self.assertTrue(subject.is_system)

    def test_reverse_migration_removes_only_initial_roles(self) -> None:
        custom_role = ParticipantRole.objects.create(
            code="custom",
            name="Vlastní role",
        )
        self.allowed_roles_migration.remove_initial_allowed_event_roles(
            apps,
            None,
        )

        self.migration.remove_initial_participant_roles(apps, None)

        self.assertFalse(
            ParticipantRole.objects.filter(
                code__in=EXPECTED_PARTICIPANT_ROLE_CODES
            ).exists()
        )
        self.assertTrue(
            ParticipantRole.objects.filter(pk=custom_role.pk).exists()
        )

    def test_migration_uses_historical_model_lookup(self) -> None:
        source = getsource(self.migration)

        self.assertIn(
            'apps.get_model("events", "ParticipantRole")',
            source,
        )
        self.assertNotIn("from events.models", source)
        self.assertNotIn("from ..models", source)
        self.assertNotIn("from .models", source)


class AllowedEventRoleDataMigrationTests(TestCase):
    """Ověření systémové matice rolí a vratnosti datové migrace."""

    migration = import_module(
        "events.migrations.0005_initial_allowed_event_roles"
    )

    def test_initial_matrix_has_exact_values(self) -> None:
        rules = set(
            AllowedEventRole.objects.values_list(
                "event_type__code",
                "participant_role__code",
                "min_count",
                "max_count",
                "sort_order",
            )
        )

        self.assertEqual(len(rules), 52)
        self.assertEqual(rules, set(EXPECTED_ALLOWED_EVENT_ROLES))
        self.assertFalse(
            AllowedEventRole.objects.filter(is_active=False).exists()
        )
        self.assertFalse(
            AllowedEventRole.objects.filter(is_system=False).exists()
        )

    def test_required_role_counts_for_each_event_type(self) -> None:
        expected_required_roles = {
            "birth": ("born_person", 1, 1),
            "baptism": ("baptized_person", 1, 1),
            "marriage": ("spouse", 2, 2),
            "divorce": ("spouse", 1, 2),
            "relocation": ("subject", 1, None),
            "education": ("subject", 1, 1),
            "graduation": ("subject", 1, 1),
            "military_service": ("subject", 1, 1),
            "employment": ("subject", 1, 1),
            "death": ("deceased_person", 1, 1),
            "funeral": ("deceased_person", 1, 1),
            "other": ("subject", 1, None),
        }

        for event_type_code, expected in expected_required_roles.items():
            with self.subTest(event_type_code=event_type_code):
                rules = AllowedEventRole.objects.filter(
                    event_type__code=event_type_code,
                    min_count__gt=0,
                ).values_list(
                    "participant_role__code",
                    "min_count",
                    "max_count",
                )
                self.assertEqual(tuple(rules), (expected,))

    def test_forward_migration_is_idempotent(self) -> None:
        AllowedEventRole.objects.filter(
            event_type__code="birth",
            participant_role__code="born_person",
        ).update(
            min_count=0,
            max_count=None,
            sort_order=999,
            is_active=False,
            is_system=False,
        )

        self.migration.create_initial_allowed_event_roles(apps, None)
        self.migration.create_initial_allowed_event_roles(apps, None)

        self.assertEqual(AllowedEventRole.objects.count(), 52)
        rule = AllowedEventRole.objects.get(
            event_type__code="birth",
            participant_role__code="born_person",
        )
        self.assertEqual(
            (
                rule.min_count,
                rule.max_count,
                rule.sort_order,
                rule.is_active,
                rule.is_system,
            ),
            (1, 1, 10, True, True),
        )

    def test_reverse_migration_removes_only_system_matrix(self) -> None:
        custom_type = EventType.objects.create(
            code="custom",
            name="Vlastní typ",
        )
        custom_role = ParticipantRole.objects.create(
            code="custom",
            name="Vlastní role",
        )
        custom_rule = AllowedEventRole.objects.create(
            event_type=custom_type,
            participant_role=custom_role,
        )

        self.migration.remove_initial_allowed_event_roles(apps, None)

        self.assertFalse(
            AllowedEventRole.objects.filter(is_system=True).exists()
        )
        self.assertTrue(
            AllowedEventRole.objects.filter(pk=custom_rule.pk).exists()
        )

    def test_missing_event_type_raises_clear_error(self) -> None:
        self.migration.remove_initial_allowed_event_roles(apps, None)
        EventType.objects.get(code="birth").delete()

        with self.assertRaisesRegex(
            RuntimeError,
            "EventType.*'birth'",
        ):
            self.migration.create_initial_allowed_event_roles(apps, None)

    def test_missing_participant_role_raises_clear_error(self) -> None:
        self.migration.remove_initial_allowed_event_roles(apps, None)
        ParticipantRole.objects.get(code="subject").delete()

        with self.assertRaisesRegex(
            RuntimeError,
            "ParticipantRole.*'subject'",
        ):
            self.migration.create_initial_allowed_event_roles(apps, None)

    def test_migration_uses_historical_model_lookups(self) -> None:
        source = getsource(self.migration)

        for model_name in (
            "EventType",
            "ParticipantRole",
            "AllowedEventRole",
        ):
            with self.subTest(model_name=model_name):
                self.assertIn(
                    f'apps.get_model("events", "{model_name}")',
                    source,
                )
        self.assertNotIn("from events.models", source)
        self.assertNotIn("from ..models", source)
        self.assertNotIn("from .models", source)


class RoleAdminTests(SimpleTestCase):
    """Ověření registrace modelů rolí v Django Adminu."""

    def test_role_models_are_registered_in_admin(self) -> None:
        self.assertTrue(admin.site.is_registered(ParticipantRole))
        self.assertTrue(admin.site.is_registered(AllowedEventRole))


class EventModelTests(SimpleTestCase):
    """Ověření struktury a metadat základního modelu události."""

    inherited_field_names = {
        "created_at",
        "updated_at",
        "access_level",
        "verification_status",
        "created_by",
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
    own_field_names = {
        "event_type",
        "place",
        "location_detail",
        "title",
        "description",
        "show_in_overview",
    }

    def test_model_is_concrete_with_exact_approved_bases(self) -> None:
        self.assertFalse(Event._meta.abstract)
        self.assertEqual(
            Event.__bases__,
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

    def test_model_has_exact_own_and_inherited_fields(self) -> None:
        field_names = {
            field.name for field in Event._meta.local_fields
        }

        self.assertEqual(
            field_names,
            {"id"} | self.inherited_field_names | self.own_field_names,
        )
        self.assertTrue(self.inherited_field_names <= field_names)
        self.assertEqual(
            field_names - self.inherited_field_names - {"id"},
            self.own_field_names,
        )

    def test_model_does_not_contain_forbidden_detail_fields(self) -> None:
        field_names = {
            field.name for field in Event._meta.local_fields
        }
        forbidden_fields = {
            "cause",
            "death_cause",
            "reason",
            "notes",
            "internal_note",
            "source",
            "attachment",
            "sort_order",
            "is_primary",
            "status",
            "participant",
            "person",
        }

        self.assertTrue(field_names.isdisjoint(forbidden_fields))

    def test_event_type_field_options(self) -> None:
        field = Event._meta.get_field("event_type")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, EventType)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(field.remote_field.related_name, "events")

    def test_place_field_options(self) -> None:
        field = Event._meta.get_field("place")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, Place)
        self.assertTrue(field.null)
        self.assertTrue(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(field.remote_field.related_name, "events")

    def test_text_field_options(self) -> None:
        location_detail = Event._meta.get_field("location_detail")
        title = Event._meta.get_field("title")
        description = Event._meta.get_field("description")

        self.assertIsInstance(location_detail, models.CharField)
        self.assertEqual(location_detail.max_length, 255)
        self.assertTrue(location_detail.blank)
        self.assertFalse(location_detail.null)
        self.assertFalse(location_detail.unique)
        self.assertIsInstance(title, models.CharField)
        self.assertEqual(title.max_length, 255)
        self.assertTrue(title.blank)
        self.assertFalse(title.null)
        self.assertFalse(title.unique)
        self.assertIsInstance(description, models.TextField)
        self.assertTrue(description.blank)
        self.assertFalse(description.null)

    def test_show_in_overview_options(self) -> None:
        field = Event._meta.get_field("show_in_overview")

        self.assertIsInstance(field, models.BooleanField)
        self.assertIs(field.default, False)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)

    def test_partial_date_sort_field_keeps_technical_index(self) -> None:
        sort_date = Event._meta.get_field("sort_date")
        sort_date_end = Event._meta.get_field("sort_date_end")

        self.assertTrue(sort_date.db_index)
        self.assertFalse(sort_date.editable)
        self.assertFalse(sort_date_end.editable)

    def test_metadata(self) -> None:
        self.assertEqual(Event._meta.verbose_name, "Událost")
        self.assertEqual(Event._meta.verbose_name_plural, "Události")
        self.assertEqual(
            Event._meta.ordering,
            ("sort_date", "sort_date_end", "pk"),
        )

    def test_string_representation_prefers_trimmed_title(self) -> None:
        event_type = EventType(code="test", name="Testovací typ")
        event = Event(
            event_type=event_type,
            title="  Vlastní název  ",
        )

        self.assertEqual(str(event), "Vlastní název")

    def test_string_representation_falls_back_to_event_type(self) -> None:
        event_type = EventType(code="test", name="Testovací typ")

        self.assertEqual(str(Event(event_type=event_type)), "Testovací typ")
        self.assertEqual(
            str(Event(event_type=event_type, title="   ")),
            "Testovací typ",
        )

    def test_string_representation_without_type_is_safe(self) -> None:
        self.assertEqual(str(Event()), "Událost")


class EventPartialDateIntegrationTests(TestCase):
    """Ověření integrace události se společným částečným datem."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.event_type = EventType.objects.create(
            code="event_date_range",
            name="Událost s rozmezím",
            supports_date_range=True,
        )

    def test_exact_date_derives_equal_sort_dates(self) -> None:
        event = Event(
            event_type=self.event_type,
            date_precision=DatePrecision.EXACT,
            start_year=1900,
            start_month=2,
            start_day=3,
        )

        event.full_clean()

        self.assertEqual(event.sort_date, date(1900, 2, 3))
        self.assertEqual(event.sort_date_end, date(1900, 2, 3))

    def test_month_derives_month_boundaries(self) -> None:
        event = Event(
            event_type=self.event_type,
            date_precision=DatePrecision.MONTH,
            start_year=1900,
            start_month=2,
        )

        event.full_clean()

        self.assertEqual(event.sort_date, date(1900, 2, 1))
        self.assertEqual(event.sort_date_end, date(1900, 2, 28))

    def test_year_derives_year_boundaries(self) -> None:
        event = Event(
            event_type=self.event_type,
            date_precision=DatePrecision.YEAR,
            start_year=1900,
        )

        event.full_clean()

        self.assertEqual(event.sort_date, date(1900, 1, 1))
        self.assertEqual(event.sort_date_end, date(1900, 12, 31))

    def test_supported_range_derives_both_boundaries(self) -> None:
        event = Event(
            event_type=self.event_type,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            start_month=2,
            end_year=1901,
            end_month=3,
        )

        event.full_clean()

        self.assertEqual(event.sort_date, date(1900, 2, 1))
        self.assertEqual(event.sort_date_end, date(1901, 3, 31))

    def test_unknown_date_is_valid_without_sort_dates(self) -> None:
        event = Event(event_type=self.event_type)

        event.full_clean()

        self.assertEqual(event.date_precision, DatePrecision.UNKNOWN)
        self.assertIsNone(event.sort_date)
        self.assertIsNone(event.sort_date_end)

    def test_qualifier_does_not_change_sort_boundaries(self) -> None:
        event = Event(
            event_type=self.event_type,
            date_precision=DatePrecision.YEAR,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1900,
        )

        event.full_clean()

        self.assertEqual(event.sort_date, date(1900, 1, 1))
        self.assertEqual(event.sort_date_end, date(1900, 12, 31))


class EventValidationTests(TestCase):
    """Ověření pravidel typu události nad datem a místem."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.range_type = EventType.objects.create(
            code="validation_range",
            name="Rozmezí a místo",
            supports_date_range=True,
            allows_place=True,
        )
        cls.single_date_type = EventType.objects.create(
            code="validation_single",
            name="Jediné datum",
            supports_date_range=False,
            allows_place=True,
        )
        cls.no_place_type = EventType.objects.create(
            code="validation_no_place",
            name="Bez místa",
            supports_date_range=True,
            allows_place=False,
        )
        cls.place = Place.objects.create(
            name="Testovací místo",
            normalized_name="testovaci misto",
        )

    def assert_field_error_code(
        self,
        event: Event,
        field_name: str,
        code: str,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn(field_name, context.exception.error_dict)
        self.assertIn(
            code,
            {
                error.code
                for error in context.exception.error_dict[field_name]
            },
        )

    def test_range_is_allowed_for_supporting_type(self) -> None:
        event = Event(
            event_type=self.range_type,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1901,
        )

        event.full_clean()

    def test_range_is_rejected_for_non_supporting_type(self) -> None:
        event = Event(
            event_type=self.single_date_type,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1901,
        )

        self.assert_field_error_code(
            event,
            "date_precision",
            "date_range_not_supported",
        )

    def test_place_is_allowed_for_supporting_type(self) -> None:
        event = Event(
            event_type=self.range_type,
            place=self.place,
        )

        event.full_clean()

    def test_place_is_rejected_for_non_supporting_type(self) -> None:
        event = Event(
            event_type=self.no_place_type,
            place=self.place,
        )

        self.assert_field_error_code(event, "place", "place_not_allowed")

    def test_location_detail_is_allowed_for_supporting_type(self) -> None:
        event = Event(
            event_type=self.range_type,
            location_detail="Dům čp. 12",
        )

        event.full_clean()

    def test_location_detail_is_rejected_for_non_supporting_type(
        self,
    ) -> None:
        event = Event(
            event_type=self.no_place_type,
            location_detail="Dům čp. 12",
        )

        self.assert_field_error_code(
            event,
            "location_detail",
            "location_detail_not_allowed",
        )

    def test_whitespace_location_detail_is_treated_as_empty(self) -> None:
        event = Event(
            event_type=self.no_place_type,
            location_detail="  \t ",
        )

        event.full_clean()

    def test_clean_aggregates_partial_date_and_event_errors(self) -> None:
        event = Event(
            event_type=self.no_place_type,
            place=self.place,
            date_precision=DatePrecision.RANGE,
            start_year=1901,
            end_year=1900,
        )

        with self.assertRaises(ValidationError) as context:
            event.full_clean()

        self.assertIn("end_year", context.exception.error_dict)
        self.assertIn("place", context.exception.error_dict)

    def test_missing_event_type_does_not_raise_related_object_error(
        self,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            Event().full_clean()

        self.assertIn("event_type", context.exception.error_dict)


class EventDatabaseTests(TestCase):
    """Ověření databázového chování a modelových defaultů události."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.event_type = EventType.objects.create(
            code="event_database",
            name="Databázový typ",
            default_show_in_overview=True,
            default_access_level=AccessLevel.RESTRICTED,
        )
        cls.place = Place.objects.create(
            name="Databázové místo",
            normalized_name="databazove misto",
        )

    def test_multiple_events_can_share_event_type(self) -> None:
        Event.objects.create(event_type=self.event_type)
        Event.objects.create(event_type=self.event_type)

        self.assertEqual(
            Event.objects.filter(event_type=self.event_type).count(),
            2,
        )

    def test_multiple_events_can_share_place(self) -> None:
        Event.objects.create(event_type=self.event_type, place=self.place)
        Event.objects.create(event_type=self.event_type, place=self.place)

        self.assertEqual(Event.objects.filter(place=self.place).count(), 2)

    def test_duplicate_titles_are_allowed(self) -> None:
        Event.objects.create(event_type=self.event_type, title="Stejný název")
        Event.objects.create(event_type=self.event_type, title="Stejný název")

        self.assertEqual(Event.objects.filter(title="Stejný název").count(), 2)

    def test_used_event_type_is_protected_from_deletion(self) -> None:
        Event.objects.create(event_type=self.event_type)

        with self.assertRaises(ProtectedError):
            self.event_type.delete()

    def test_used_place_is_protected_from_deletion(self) -> None:
        Event.objects.create(event_type=self.event_type, place=self.place)

        with self.assertRaises(ProtectedError):
            self.place.delete()

    def test_event_type_defaults_are_not_copied_automatically(self) -> None:
        event = Event(event_type=self.event_type)

        self.assertEqual(event.access_level, AccessLevel.PUBLIC)
        self.assertFalse(event.show_in_overview)

        event.save()
        event.refresh_from_db()

        self.assertEqual(event.access_level, AccessLevel.PUBLIC)
        self.assertFalse(event.show_in_overview)

    def test_event_type_default_changes_do_not_update_existing_event(
        self,
    ) -> None:
        event = Event.objects.create(
            event_type=self.event_type,
            access_level=AccessLevel.AUTHENTICATED,
            show_in_overview=True,
        )
        self.event_type.default_access_level = AccessLevel.ADMIN_ONLY
        self.event_type.default_show_in_overview = False
        self.event_type.save(
            update_fields=(
                "default_access_level",
                "default_show_in_overview",
            )
        )

        event.refresh_from_db()

        self.assertEqual(event.access_level, AccessLevel.AUTHENTICATED)
        self.assertTrue(event.show_in_overview)


class EventMigrationTests(SimpleTestCase):
    """Ověření rozsahu a závislostí strukturální migrace Event."""

    migration = import_module("events.migrations.0006_event")

    def test_migration_contains_only_event_create_model(self) -> None:
        operations = self.migration.Migration.operations

        self.assertEqual(len(operations), 1)
        self.assertIsInstance(operations[0], migrations.CreateModel)
        self.assertEqual(operations[0].name, "Event")

    def test_migration_has_exact_dependencies(self) -> None:
        self.assertCountEqual(
            self.migration.Migration.dependencies,
            (
                ("events", "0005_initial_allowed_event_roles"),
                ("places", "0002_place"),
                migrations.swappable_dependency(
                    settings.AUTH_USER_MODEL
                ),
            ),
        )


class EventAdminTests(SimpleTestCase):
    """Ověření jednoduché registrace události v Django Adminu."""

    def test_event_is_registered_in_admin(self) -> None:
        self.assertFalse(admin.site.is_registered(Event))


class EventParticipantModelTests(SimpleTestCase):
    """Ověření struktury a metadat účastníka události."""

    def test_model_is_concrete_direct_model_subclass(self) -> None:
        self.assertFalse(EventParticipant._meta.abstract)
        self.assertEqual(EventParticipant.__bases__, (models.Model,))

        for common_model in (
            TimestampedModel,
            AccessControlledModel,
            VerifiableModel,
            AuthoredModel,
            LifecycleModel,
            PartialDateModel,
            LookupModel,
        ):
            with self.subTest(common_model=common_model.__name__):
                self.assertNotIn(common_model, EventParticipant.__mro__)

    def test_model_has_only_expected_fields(self) -> None:
        self.assertEqual(
            {field.name for field in EventParticipant._meta.local_fields},
            {"id", "event", "person", "role", "note"},
        )

    def test_event_field_options(self) -> None:
        field = EventParticipant._meta.get_field("event")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, Event)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertIs(field.remote_field.on_delete, models.CASCADE)
        self.assertEqual(field.remote_field.related_name, "participants")

    def test_person_field_options(self) -> None:
        field = EventParticipant._meta.get_field("person")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, Person)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(
            field.remote_field.related_name,
            "event_participations",
        )

    def test_role_field_options(self) -> None:
        field = EventParticipant._meta.get_field("role")

        self.assertIsInstance(field, models.ForeignKey)
        self.assertIs(field.remote_field.model, ParticipantRole)
        self.assertFalse(field.null)
        self.assertFalse(field.blank)
        self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(
            field.remote_field.related_name,
            "event_participations",
        )

    def test_note_field_options_and_default(self) -> None:
        field = EventParticipant._meta.get_field("note")

        self.assertIsInstance(field, models.TextField)
        self.assertTrue(field.blank)
        self.assertFalse(field.null)
        self.assertFalse(field.unique)
        self.assertEqual(EventParticipant().note, "")

    def test_metadata_and_constraint(self) -> None:
        self.assertEqual(
            EventParticipant._meta.ordering,
            (
                "role__sort_order",
                "person__last_name",
                "person__first_name",
                "person_id",
            ),
        )
        self.assertEqual(
            EventParticipant._meta.verbose_name,
            "Účastník události",
        )
        self.assertEqual(
            EventParticipant._meta.verbose_name_plural,
            "Účastníci událostí",
        )

        self.assertEqual(len(EventParticipant._meta.constraints), 1)
        constraint = EventParticipant._meta.constraints[0]
        self.assertIsInstance(constraint, models.UniqueConstraint)
        self.assertEqual(constraint.name, "events_unique_participation")
        self.assertEqual(
            constraint.fields,
            ("event", "person", "role"),
        )

    def test_model_does_not_override_clean_or_save(self) -> None:
        self.assertIs(EventParticipant.clean, models.Model.clean)
        self.assertIs(EventParticipant.save, models.Model.save)

    def test_string_representation_with_available_relations(self) -> None:
        participant = EventParticipant(
            event=Event(
                event_type=EventType(code="test", name="Typ"),
                title="Testovací událost",
            ),
            person=Person(first_name="Jan", last_name="Novák"),
            role=ParticipantRole(code="witness", name="Svědek"),
        )

        self.assertEqual(
            str(participant),
            "Novák Jan – Svědek – Testovací událost",
        )

    def test_string_representation_falls_back_without_person(self) -> None:
        participant = EventParticipant(
            event=Event(title="Testovací událost"),
            role=ParticipantRole(code="witness", name="Svědek"),
        )

        self.assertEqual(
            str(participant),
            "Neznámá osoba – Svědek – Testovací událost",
        )

    def test_string_representation_falls_back_without_role(self) -> None:
        participant = EventParticipant(
            event=Event(title="Testovací událost"),
            person=Person(first_name="Jan", last_name="Novák"),
        )

        self.assertEqual(
            str(participant),
            "Novák Jan – Neznámá role – Testovací událost",
        )

    def test_string_representation_falls_back_without_event(self) -> None:
        participant = EventParticipant(
            person=Person(first_name="Jan", last_name="Novák"),
            role=ParticipantRole(code="witness", name="Svědek"),
        )

        self.assertEqual(
            str(participant),
            "Novák Jan – Svědek – Událost",
        )

    def test_string_representation_of_empty_instance_is_safe(self) -> None:
        self.assertEqual(
            str(EventParticipant()),
            "Neznámá osoba – Neznámá role – Událost",
        )


class EventParticipantDatabaseTests(TestCase):
    """Ověření referenční integrity a unikátnosti účastí."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.event_type = EventType.objects.create(
            code="participant_test",
            name="Testovací typ účasti",
        )
        cls.first_event = Event.objects.create(
            event_type=cls.event_type,
            title="První událost",
        )
        cls.second_event = Event.objects.create(
            event_type=cls.event_type,
            title="Druhá událost",
        )
        cls.first_person = Person.objects.create(
            first_name="Jan",
            last_name="Novák",
        )
        cls.second_person = Person.objects.create(
            first_name="Petr",
            last_name="Novák",
        )
        cls.first_role = ParticipantRole.objects.create(
            code="participant_first",
            name="První role",
        )
        cls.second_role = ParticipantRole.objects.create(
            code="participant_second",
            name="Druhá role",
        )

    def test_event_can_have_multiple_participants(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.second_person,
            role=self.first_role,
        )

        self.assertEqual(self.first_event.participants.count(), 2)

    def test_deleting_event_cascades_to_participants(self) -> None:
        participant = EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )

        self.first_event.delete()

        self.assertFalse(
            EventParticipant.objects.filter(pk=participant.pk).exists()
        )

    def test_used_person_is_protected_from_deletion(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )

        with self.assertRaises(ProtectedError):
            self.first_person.delete()

    def test_used_role_is_protected_from_deletion(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )

        with self.assertRaises(ProtectedError):
            self.first_role.delete()

    def test_same_person_can_participate_in_multiple_events(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )
        EventParticipant.objects.create(
            event=self.second_event,
            person=self.first_person,
            role=self.first_role,
        )

        self.assertEqual(
            self.first_person.event_participations.count(),
            2,
        )

    def test_same_person_can_have_multiple_roles_in_event(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.second_role,
        )

        self.assertEqual(
            EventParticipant.objects.filter(
                event=self.first_event,
                person=self.first_person,
            ).count(),
            2,
        )

    def test_same_role_can_be_used_by_multiple_people(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.second_person,
            role=self.first_role,
        )

        self.assertEqual(
            self.first_role.event_participations.count(),
            2,
        )

    def test_duplicate_event_person_role_is_rejected(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventParticipant.objects.create(
                    event=self.first_event,
                    person=self.first_person,
                    role=self.first_role,
                )

    def test_different_note_does_not_allow_duplicate(self) -> None:
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
            note="První poznámka",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventParticipant.objects.create(
                    event=self.first_event,
                    person=self.first_person,
                    role=self.first_role,
                    note="Druhá poznámka",
                )

    def test_model_does_not_validate_allowed_event_role(self) -> None:
        self.assertFalse(
            AllowedEventRole.objects.filter(
                event_type=self.event_type,
                participant_role=self.first_role,
            ).exists()
        )
        participant = EventParticipant(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )

        participant.full_clean()
        participant.save()

        self.assertTrue(
            EventParticipant.objects.filter(pk=participant.pk).exists()
        )

    def test_model_does_not_enforce_allowed_role_maximum(self) -> None:
        AllowedEventRole.objects.create(
            event_type=self.event_type,
            participant_role=self.first_role,
            max_count=1,
        )

        EventParticipant.objects.create(
            event=self.first_event,
            person=self.first_person,
            role=self.first_role,
        )
        EventParticipant.objects.create(
            event=self.first_event,
            person=self.second_person,
            role=self.first_role,
        )

        self.assertEqual(
            EventParticipant.objects.filter(
                event=self.first_event,
                role=self.first_role,
            ).count(),
            2,
        )


class EventParticipantMigrationTests(SimpleTestCase):
    """Ověření rozsahu strukturální migrace účastníka události."""

    migration = import_module(
        "events.migrations.0007_event_participant"
    )

    def test_migration_contains_only_participant_create_model(self) -> None:
        operations = self.migration.Migration.operations

        self.assertEqual(len(operations), 1)
        self.assertIsInstance(operations[0], migrations.CreateModel)
        self.assertEqual(operations[0].name, "EventParticipant")
        self.assertEqual(
            len(operations[0].options["constraints"]),
            1,
        )

    def test_migration_has_exact_dependencies(self) -> None:
        self.assertCountEqual(
            self.migration.Migration.dependencies,
            (
                ("events", "0006_event"),
                ("people", "0003_person"),
            ),
        )


class EventParticipantAdminTests(SimpleTestCase):
    """Ověření jednoduché registrace účastníka v Django Adminu."""

    def test_event_participant_is_registered_in_admin(self) -> None:
        self.assertFalse(admin.site.is_registered(EventParticipant))
