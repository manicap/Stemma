from importlib import import_module
from inspect import getsource

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from common.choices import AccessLevel
from common.models import LookupModel

from .apps import EventsConfig
from .models import AllowedEventRole, EventType, ParticipantRole


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
