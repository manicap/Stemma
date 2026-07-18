from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.choices import AccessLevel
from common.models import LookupModel

from .apps import EventsConfig
from .models import EventType


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
