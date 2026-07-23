from importlib import import_module

from django.apps import apps
from django.contrib import admin
from django.db import IntegrityError, models, transaction
from django.test import SimpleTestCase, TestCase

from common.models import LookupModel

from .admin import GraveSiteTypeAdmin, PersonGraveSiteRoleAdmin
from .models import (
    GraveSiteType,
    PersonGraveSiteRole,
    ResidenceType,
)


EXPECTED_GRAVE_SITE_TYPES = (
    {
        "code": "grave",
        "name": "Hrob",
        "description": (
            "Hrobové místo určené k uložení tělesných ostatků; může být "
            "individuální i společné."
        ),
        "sort_order": 10,
    },
    {
        "code": "tomb",
        "name": "Hrobka",
        "description": (
            "Stavebně vymezené hrobové místo nebo podzemní či nadzemní "
            "hrobka."
        ),
        "sort_order": 20,
    },
    {
        "code": "urn_site",
        "name": "Urnové místo",
        "description": (
            "Místo určené k uložení urny, včetně urnového hrobu nebo "
            "jednotlivé kolumbární schránky."
        ),
        "sort_order": 30,
    },
    {
        "code": "ossuary",
        "name": "Kostnice",
        "description": "Místo společného uložení kosterních ostatků.",
        "sort_order": 40,
    },
    {
        "code": "scattering_place",
        "name": "Místo rozptylu",
        "description": (
            "Vymezené místo, na kterém byl proveden rozptyl popela."
        ),
        "sort_order": 50,
    },
    {
        "code": "memorial",
        "name": "Pamětní místo",
        "description": (
            "Památník, deska nebo jiné místo připomínky bez tvrzení o "
            "uložení ostatků."
        ),
        "sort_order": 60,
    },
    {
        "code": "cenotaph",
        "name": "Symbolický hrob",
        "description": (
            "Hrob nebo památník připomínající osobu, jejíž ostatky zde "
            "nejsou uloženy."
        ),
        "sort_order": 70,
    },
    {
        "code": "other",
        "name": "Jiné místo",
        "description": (
            "Jiný druh hrobového, pohřebního nebo pamětního místa."
        ),
        "sort_order": 90,
    },
)

EXPECTED_PERSON_GRAVE_SITE_ROLES = (
    {
        "code": "buried",
        "name": "Pohřbena",
        "description": "Na místě byly uloženy tělesné ostatky osoby.",
        "sort_order": 10,
    },
    {
        "code": "urn_placed",
        "name": "Uložena urna",
        "description": "Na místě byla uložena urna s popelem osoby.",
        "sort_order": 20,
    },
    {
        "code": "ashes_scattered",
        "name": "Rozptýlena",
        "description": "Na místě byl rozptýlen popel osoby.",
        "sort_order": 30,
    },
    {
        "code": "commemorated",
        "name": "Připomenuta",
        "description": (
            "Osoba je na místě připomenuta nápisem, památníkem nebo "
            "symbolicky, bez tvrzení o uložení ostatků."
        ),
        "sort_order": 40,
    },
    {
        "code": "remains_relocated_from",
        "name": "Ostatky přemístěny z místa",
        "description": (
            "Místo je doloženým výchozím místem přemístění ostatků."
        ),
        "sort_order": 50,
    },
    {
        "code": "remains_relocated_to",
        "name": "Ostatky přemístěny na místo",
        "description": (
            "Místo je doloženým cílem přemístění ostatků."
        ),
        "sort_order": 60,
    },
    {
        "code": "other",
        "name": "Jiné propojení",
        "description": "Jiný význam propojení osoby s místem.",
        "sort_order": 90,
    },
)

EXPECTED_TYPE_CODES = tuple(
    grave_site_type["code"]
    for grave_site_type in EXPECTED_GRAVE_SITE_TYPES
)
EXPECTED_ROLE_CODES = tuple(
    role["code"] for role in EXPECTED_PERSON_GRAVE_SITE_ROLES
)
LOOKUP_FIELD_NAMES = (
    "id",
    "code",
    "name",
    "description",
    "sort_order",
    "is_active",
    "is_system",
)


class GraveSiteLookupModelTests(SimpleTestCase):
    """Ověření struktury a metadat obou rozšiřitelných katalogů."""

    def test_models_are_concrete_direct_lookup_subclasses(self) -> None:
        for model in (GraveSiteType, PersonGraveSiteRole):
            with self.subTest(model=model.__name__):
                self.assertFalse(model._meta.abstract)
                self.assertEqual(model.__bases__, (LookupModel,))
                self.assertIs(
                    apps.get_model("places", model.__name__),
                    model,
                )

    def test_models_have_only_lookup_fields(self) -> None:
        for model in (GraveSiteType, PersonGraveSiteRole):
            with self.subTest(model=model.__name__):
                self.assertEqual(
                    tuple(field.name for field in model._meta.local_fields),
                    LOOKUP_FIELD_NAMES,
                )

    def test_metadata_ordering_and_string_representation(self) -> None:
        expectations = (
            (
                GraveSiteType,
                "Typ hrobového místa",
                "Typy hrobových míst",
            ),
            (
                PersonGraveSiteRole,
                "Role osoby u hrobového místa",
                "Role osob u hrobových míst",
            ),
        )
        for model, verbose_name, verbose_name_plural in expectations:
            with self.subTest(model=model.__name__):
                instance = model(code="test", name="Testovací hodnota")
                self.assertEqual(
                    model._meta.ordering,
                    ("sort_order", "name", "code"),
                )
                self.assertEqual(model._meta.verbose_name, verbose_name)
                self.assertEqual(
                    model._meta.verbose_name_plural,
                    verbose_name_plural,
                )
                self.assertEqual(str(instance), "Testovací hodnota")


class GraveSiteLookupDatabaseTests(TestCase):
    """Ověření uživatelských hodnot a databázové integrity."""

    def test_user_values_use_lookup_defaults(self) -> None:
        grave_site_type = GraveSiteType.objects.create(
            code="user_type",
            name="Uživatelský typ",
        )
        role = PersonGraveSiteRole.objects.create(
            code="user_role",
            name="Uživatelská role",
        )

        for value in (grave_site_type, role):
            with self.subTest(model=type(value).__name__):
                value.refresh_from_db()
                self.assertTrue(value.is_active)
                self.assertFalse(value.is_system)
                self.assertEqual(value.sort_order, 0)

    def test_code_is_unique_within_each_catalog(self) -> None:
        for model in (GraveSiteType, PersonGraveSiteRole):
            with self.subTest(model=model.__name__):
                model.objects.create(code="duplicate", name="První")
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        model.objects.create(
                            code="duplicate",
                            name="Druhý",
                        )

    def test_same_code_can_exist_in_both_catalogs(self) -> None:
        self.assertTrue(
            GraveSiteType.objects.filter(code="other").exists()
        )
        self.assertTrue(
            PersonGraveSiteRole.objects.filter(code="other").exists()
        )


class GraveSiteLookupSystemDataTests(TestCase):
    """Ověření přesných aplikovaných systémových katalogů."""

    def test_grave_site_type_catalog_is_exact(self) -> None:
        system_values = GraveSiteType.objects.filter(is_system=True)

        self.assertEqual(system_values.count(), 8)
        self.assertEqual(
            list(
                system_values.values(
                    "code",
                    "name",
                    "description",
                    "sort_order",
                )
            ),
            list(EXPECTED_GRAVE_SITE_TYPES),
        )
        self.assertFalse(system_values.filter(is_active=False).exists())
        self.assertEqual(
            list(system_values.values_list("code", flat=True)),
            list(EXPECTED_TYPE_CODES),
        )

    def test_person_grave_site_role_catalog_is_exact(self) -> None:
        system_values = PersonGraveSiteRole.objects.filter(is_system=True)

        self.assertEqual(system_values.count(), 7)
        self.assertEqual(
            list(
                system_values.values(
                    "code",
                    "name",
                    "description",
                    "sort_order",
                )
            ),
            list(EXPECTED_PERSON_GRAVE_SITE_ROLES),
        )
        self.assertFalse(system_values.filter(is_active=False).exists())
        self.assertEqual(
            list(system_values.values_list("code", flat=True)),
            list(EXPECTED_ROLE_CODES),
        )

    def test_forbidden_system_codes_are_absent(self) -> None:
        self.assertFalse(
            GraveSiteType.objects.filter(
                code__in=("family_grave", "columbarium", "urn_grave"),
                is_system=True,
            ).exists()
        )
        self.assertFalse(
            PersonGraveSiteRole.objects.filter(
                code__in=("remains_relocated", "cenotaph"),
                is_system=True,
            ).exists()
        )


class GraveSiteLookupMigrationHelperTests(TestCase):
    """Ověření idempotence, společných kolizí a reverse migrace."""

    migration = import_module(
        "places.migrations.0007_initial_grave_site_lookups"
    )

    def test_forward_is_idempotent_and_repairs_both_catalogs(self) -> None:
        GraveSiteType.objects.filter(code="grave").update(
            name="Změněný typ",
            description="Změněný popis typu.",
            sort_order=999,
            is_active=False,
        )
        PersonGraveSiteRole.objects.filter(code="buried").update(
            name="Změněná role",
            description="Změněný popis role.",
            sort_order=999,
            is_active=False,
        )

        self.migration.create_initial_grave_site_lookups(apps, None)
        self.migration.create_initial_grave_site_lookups(apps, None)

        self.assertEqual(
            GraveSiteType.objects.filter(is_system=True).count(),
            8,
        )
        self.assertEqual(
            PersonGraveSiteRole.objects.filter(is_system=True).count(),
            7,
        )
        grave = GraveSiteType.objects.get(code="grave")
        buried = PersonGraveSiteRole.objects.get(code="buried")
        self.assertEqual(grave.name, "Hrob")
        self.assertEqual(
            grave.description,
            "Hrobové místo určené k uložení tělesných ostatků; může být "
            "individuální i společné.",
        )
        self.assertEqual(grave.sort_order, 10)
        self.assertTrue(grave.is_active)
        self.assertEqual(buried.name, "Pohřbena")
        self.assertEqual(
            buried.description,
            "Na místě byly uloženy tělesné ostatky osoby.",
        )
        self.assertEqual(buried.sort_order, 10)
        self.assertTrue(buried.is_active)

    def test_grave_site_type_collision_prevents_all_writes(self) -> None:
        GraveSiteType.objects.all().delete()
        PersonGraveSiteRole.objects.all().delete()
        conflict = GraveSiteType.objects.create(
            code="grave",
            name="Uživatelský konflikt typu",
        )
        existing_role = PersonGraveSiteRole.objects.create(
            code="buried",
            name="Původní systémová role",
            description="Nesmí se změnit.",
            sort_order=777,
            is_active=False,
            is_system=True,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "GraveSiteType: grave",
        ):
            self.migration.create_initial_grave_site_lookups(apps, None)

        conflict.refresh_from_db()
        existing_role.refresh_from_db()
        self.assertEqual(conflict.name, "Uživatelský konflikt typu")
        self.assertFalse(conflict.is_system)
        self.assertEqual(existing_role.name, "Původní systémová role")
        self.assertEqual(existing_role.description, "Nesmí se změnit.")
        self.assertEqual(existing_role.sort_order, 777)
        self.assertFalse(existing_role.is_active)
        self.assertEqual(GraveSiteType.objects.count(), 1)
        self.assertEqual(PersonGraveSiteRole.objects.count(), 1)

    def test_person_role_collision_prevents_all_writes(self) -> None:
        GraveSiteType.objects.all().delete()
        PersonGraveSiteRole.objects.all().delete()
        existing_type = GraveSiteType.objects.create(
            code="grave",
            name="Původní systémový typ",
            description="Nesmí se změnit.",
            sort_order=777,
            is_active=False,
            is_system=True,
        )
        conflict = PersonGraveSiteRole.objects.create(
            code="buried",
            name="Uživatelský konflikt role",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "PersonGraveSiteRole: buried",
        ):
            self.migration.create_initial_grave_site_lookups(apps, None)

        existing_type.refresh_from_db()
        conflict.refresh_from_db()
        self.assertEqual(existing_type.name, "Původní systémový typ")
        self.assertEqual(existing_type.description, "Nesmí se změnit.")
        self.assertEqual(existing_type.sort_order, 777)
        self.assertFalse(existing_type.is_active)
        self.assertEqual(conflict.name, "Uživatelský konflikt role")
        self.assertFalse(conflict.is_system)
        self.assertEqual(GraveSiteType.objects.count(), 1)
        self.assertEqual(PersonGraveSiteRole.objects.count(), 1)

    def test_reverse_removes_only_current_system_catalog_rows(self) -> None:
        GraveSiteType.objects.filter(code="other").update(is_system=False)
        PersonGraveSiteRole.objects.filter(code="other").update(
            is_system=False
        )
        user_type = GraveSiteType.objects.create(
            code="user_reverse_type",
            name="Uživatelský typ",
        )
        user_role = PersonGraveSiteRole.objects.create(
            code="user_reverse_role",
            name="Uživatelská role",
        )
        residence_type = ResidenceType.objects.create(
            code="reverse_residence_type",
            name="Typ bydliště",
        )

        self.migration.remove_initial_grave_site_lookups(apps, None)

        self.assertEqual(
            set(GraveSiteType.objects.values_list("code", flat=True)),
            {"other", user_type.code},
        )
        self.assertEqual(
            set(
                PersonGraveSiteRole.objects.values_list(
                    "code",
                    flat=True,
                )
            ),
            {"other", user_role.code},
        )
        self.assertFalse(
            GraveSiteType.objects.get(code="other").is_system
        )
        self.assertFalse(
            PersonGraveSiteRole.objects.get(code="other").is_system
        )
        self.assertTrue(
            ResidenceType.objects.filter(pk=residence_type.pk).exists()
        )


class GraveSiteLookupAdminTests(SimpleTestCase):
    """Ověření lokální konfigurace obou katalogů v Django Adminu."""

    expected_list_display = (
        "code",
        "name",
        "sort_order",
        "is_active",
        "is_system",
    )

    def test_models_are_registered_with_exact_configuration(self) -> None:
        expectations = (
            (GraveSiteType, GraveSiteTypeAdmin),
            (PersonGraveSiteRole, PersonGraveSiteRoleAdmin),
        )
        for model, admin_class in expectations:
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))
                model_admin = admin.site._registry[model]
                self.assertIsInstance(model_admin, admin_class)
                self.assertEqual(
                    model_admin.list_display,
                    self.expected_list_display,
                )
                self.assertEqual(
                    model_admin.search_fields,
                    ("code", "name"),
                )
                self.assertEqual(
                    model_admin.list_filter,
                    ("is_active", "is_system"),
                )
