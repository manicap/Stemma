from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from people.models import Person

from .admin import PersonGraveSiteAdmin
from .choices import GraveSiteStatus
from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
)


class PersonGraveSiteModelTests(SimpleTestCase):
    """Ověření struktury a metadat spojovacího modelu."""

    inherited_field_names = {
        "id",
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
    }

    def test_model_is_concrete_and_uses_exact_mixins(self) -> None:
        self.assertFalse(PersonGraveSite._meta.abstract)
        self.assertEqual(
            PersonGraveSite.__bases__,
            (
                TimestampedModel,
                AccessControlledModel,
                VerifiableModel,
                AuthoredModel,
                LifecycleModel,
                models.Model,
            ),
        )
        self.assertNotIn(PartialDateModel, PersonGraveSite.__bases__)
        self.assertIs(
            apps.get_model("places", "PersonGraveSite"),
            PersonGraveSite,
        )

    def test_model_has_only_approved_own_fields(self) -> None:
        own_fields = tuple(
            field.name
            for field in PersonGraveSite._meta.local_fields
            if field.name not in self.inherited_field_names
        )

        self.assertEqual(
            own_fields,
            ("person", "grave_site", "role", "note"),
        )

    def test_inherited_fields_are_present_once(self) -> None:
        field_names = [
            field.name for field in PersonGraveSite._meta.local_fields
        ]

        self.assertTrue(self.inherited_field_names <= set(field_names))
        for field_name in self.inherited_field_names:
            with self.subTest(field_name=field_name):
                self.assertEqual(field_names.count(field_name), 1)

    def test_model_has_no_partial_date_fields(self) -> None:
        field_names = {
            field.name for field in PersonGraveSite._meta.local_fields
        }

        for forbidden_field in (
            "start_year",
            "start_month",
            "start_day",
            "end_year",
            "end_month",
            "end_day",
            "date_precision",
            "date_qualifier",
            "sort_date",
            "sort_date_end",
        ):
            with self.subTest(field_name=forbidden_field):
                self.assertNotIn(forbidden_field, field_names)

    def test_foreign_keys_have_exact_contract(self) -> None:
        expectations = {
            "person": (Person, "grave_site_links"),
            "grave_site": (GraveSite, "person_links"),
            "role": (
                PersonGraveSiteRole,
                "person_grave_site_links",
            ),
        }

        for field_name, (target, related_name) in expectations.items():
            with self.subTest(field_name=field_name):
                field = PersonGraveSite._meta.get_field(field_name)
                self.assertIsInstance(field, models.ForeignKey)
                self.assertIs(field.remote_field.model, target)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
                self.assertEqual(field.remote_field.related_name, related_name)
                self.assertFalse(field.null)
                self.assertFalse(field.blank)

    def test_note_meta_constraints_and_indexes_have_exact_contract(
        self,
    ) -> None:
        note = PersonGraveSite._meta.get_field("note")

        self.assertIsInstance(note, models.TextField)
        self.assertTrue(note.blank)
        self.assertFalse(note.null)
        self.assertEqual(
            PersonGraveSite._meta.verbose_name,
            "Propojení osoby s hrobovým místem",
        )
        self.assertEqual(
            PersonGraveSite._meta.verbose_name_plural,
            "Propojení osob s hrobovými místy",
        )
        self.assertEqual(
            PersonGraveSite._meta.ordering,
            (
                "person_id",
                "grave_site_id",
                "role__sort_order",
                "role__name",
                "pk",
            ),
        )
        self.assertEqual(PersonGraveSite._meta.constraints, [])
        self.assertEqual(PersonGraveSite._meta.indexes, [])

    def test_model_defines_no_custom_clean(self) -> None:
        self.assertNotIn("clean", PersonGraveSite.__dict__)

    def test_string_contains_person_role_and_grave_site(self) -> None:
        person = Person(pk=1, first_name="Jan", last_name="Novák")
        role = PersonGraveSiteRole(
            pk=1,
            code="buried",
            name="Pohřbena",
        )
        grave_site_type = GraveSiteType(
            pk=1,
            code="grave",
            name="Hrob",
        )
        grave_site = GraveSite(
            pk=1,
            grave_site_type=grave_site_type,
            cemetery_name="Městský hřbitov",
        )

        self.assertEqual(
            str(
                PersonGraveSite(
                    person=person,
                    grave_site=grave_site,
                    role=role,
                )
            ),
            "Novák Jan – Pohřbena – Městský hřbitov – Hrob",
        )

    def test_string_is_defensive_for_missing_relations(self) -> None:
        self.assertEqual(
            str(PersonGraveSite()),
            "Neznámá osoba – Neznámá role – Hrobové místo",
        )


class PersonGraveSiteDatabaseTests(TestCase):
    """Ověření databázového chování explicitní vazby."""

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Jan",
            last_name="Novák",
        )
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.grave_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            cemetery_name="Městský hřbitov",
        )
        self.role = PersonGraveSiteRole.objects.get(code="buried")

    def create_link(self, **overrides: object) -> PersonGraveSite:
        values = {
            "person": self.person,
            "grave_site": self.grave_site,
            "role": self.role,
        }
        values.update(overrides)
        link = PersonGraveSite(**values)
        link.full_clean()
        link.save()
        return link

    def test_all_system_roles_and_user_role_are_allowed(self) -> None:
        role_codes = (
            "buried",
            "urn_placed",
            "ashes_scattered",
            "commemorated",
            "remains_relocated_from",
            "remains_relocated_to",
        )
        for index, role_code in enumerate(role_codes, start=1):
            with self.subTest(role_code=role_code):
                role = PersonGraveSiteRole.objects.get(code=role_code)
                link = self.create_link(
                    role=role,
                    note=f"Tvrzení {index}",
                )
                self.assertEqual(link.role, role)

        user_role = PersonGraveSiteRole.objects.create(
            code="family_tradition",
            name="Rodinná tradice",
        )
        link = self.create_link(role=user_role)
        self.assertFalse(user_role.is_system)
        self.assertEqual(link.role, user_role)

    def test_inactive_role_is_allowed_by_model_layer(self) -> None:
        inactive_role = PersonGraveSiteRole.objects.create(
            code="inactive_role",
            name="Neaktivní role",
            is_active=False,
        )

        link = self.create_link(role=inactive_role)

        self.assertEqual(link.role, inactive_role)

    def test_multiple_people_sites_and_roles_are_allowed(self) -> None:
        second_person = Person.objects.create(
            first_name="Marie",
            last_name="Nováková",
        )
        second_site = GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            location_text="Druhé místo",
        )
        second_role = PersonGraveSiteRole.objects.get(code="commemorated")

        first = self.create_link()
        second = self.create_link(person=second_person)
        third = self.create_link(grave_site=second_site)
        fourth = self.create_link(role=second_role)

        self.assertEqual(self.grave_site.person_links.count(), 3)
        self.assertEqual(self.person.grave_site_links.count(), 3)
        self.assertEqual(
            {first.role, fourth.role},
            {self.role, second_role},
        )
        self.assertEqual(second.person, second_person)
        self.assertEqual(third.grave_site, second_site)

    def test_exact_duplicate_claims_are_allowed(self) -> None:
        first = self.create_link()
        second = self.create_link()

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(PersonGraveSite.objects.count(), 2)

    def test_unusual_role_and_site_type_combination_is_allowed(self) -> None:
        memorial_type = GraveSiteType.objects.get(code="memorial")
        memorial = GraveSite.objects.create(
            grave_site_type=memorial_type,
            location_text="Pamětní deska",
        )

        link = self.create_link(
            grave_site=memorial,
            role=self.role,
        )

        self.assertEqual(link.role.code, "buried")
        self.assertEqual(link.grave_site.grave_site_type.code, "memorial")

    def test_lifecycle_is_independent_from_person_site_and_status(
        self,
    ) -> None:
        link = self.create_link()
        now = timezone.now()

        PersonGraveSite.objects.filter(pk=link.pk).update(archived_at=now)
        link.refresh_from_db()
        self.person.refresh_from_db()
        self.grave_site.refresh_from_db()
        self.assertEqual(link.archived_at, now)
        self.assertIsNone(self.person.archived_at)
        self.assertIsNone(self.grave_site.archived_at)
        self.assertEqual(self.grave_site.status, GraveSiteStatus.UNKNOWN)

        PersonGraveSite.objects.filter(pk=link.pk).update(deleted_at=now)
        link.refresh_from_db()
        self.person.refresh_from_db()
        self.grave_site.refresh_from_db()
        self.assertEqual(link.deleted_at, now)
        self.assertIsNone(self.person.deleted_at)
        self.assertIsNone(self.grave_site.deleted_at)
        self.assertEqual(self.grave_site.status, GraveSiteStatus.UNKNOWN)

        self.grave_site.status = GraveSiteStatus.DESTROYED
        self.grave_site.save(update_fields=("status",))
        link.refresh_from_db()
        self.assertEqual(link.archived_at, now)
        self.assertEqual(link.deleted_at, now)

    def test_access_and_verification_are_independent(self) -> None:
        self.person.access_level = AccessLevel.RESTRICTED
        self.person.verification_status = VerificationStatus.PROBABLE
        self.person.save(
            update_fields=("access_level", "verification_status")
        )
        self.grave_site.access_level = AccessLevel.ADMIN_ONLY
        self.grave_site.verification_status = VerificationStatus.DISPUTED
        self.grave_site.save(
            update_fields=("access_level", "verification_status")
        )

        default_link = self.create_link()
        explicit_link = self.create_link(
            access_level=AccessLevel.AUTHENTICATED,
            verification_status=VerificationStatus.VERIFIED,
        )

        self.assertEqual(default_link.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            default_link.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(
            explicit_link.access_level,
            AccessLevel.AUTHENTICATED,
        )
        self.assertEqual(
            explicit_link.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertNotEqual(
            explicit_link.access_level,
            self.person.access_level,
        )
        self.assertNotEqual(
            explicit_link.access_level,
            self.grave_site.access_level,
        )

    def test_person_grave_site_and_role_are_protected(self) -> None:
        protected_person = Person.objects.create(
            first_name="Chráněná",
            last_name="Osoba",
        )
        protected_type = GraveSiteType.objects.create(
            code="protected_link_type",
            name="Chráněný typ",
        )
        protected_site = GraveSite.objects.create(
            grave_site_type=protected_type,
            location_text="Chráněné místo",
        )
        protected_role = PersonGraveSiteRole.objects.create(
            code="protected_role",
            name="Chráněná role",
        )
        self.create_link(
            person=protected_person,
            grave_site=protected_site,
            role=protected_role,
        )

        for protected_object in (
            protected_person,
            protected_site,
            protected_role,
        ):
            with self.subTest(model=type(protected_object).__name__):
                with self.assertRaises(ProtectedError):
                    with transaction.atomic():
                        protected_object.delete()

    def test_note_preserves_text_and_timestamps_are_populated(self) -> None:
        actor = get_user_model().objects.create_user(
            username="grave-link-author"
        )
        long_note = "  Historická poznámka " + ("x" * 1200) + "  "

        link = self.create_link(note=long_note, created_by=actor)
        link.refresh_from_db()

        self.assertEqual(link.note, long_note)
        self.assertEqual(link.created_by, actor)
        self.assertIsNotNone(link.created_at)
        self.assertIsNotNone(link.updated_at)

    def test_empty_note_is_allowed(self) -> None:
        link = self.create_link(note="")

        self.assertEqual(link.note, "")

    def test_string_works_for_different_grave_site_types(self) -> None:
        memorial_type = GraveSiteType.objects.get(code="memorial")
        memorial = GraveSite.objects.create(
            grave_site_type=memorial_type,
            location_text="Pamětní deska",
        )
        role = PersonGraveSiteRole.objects.get(code="commemorated")

        link = self.create_link(grave_site=memorial, role=role)
        text = str(link)

        self.assertIn(str(self.person), text)
        self.assertIn(str(role), text)
        self.assertIn(str(memorial), text)


class PersonGraveSiteAdminTests(SimpleTestCase):
    """Ověření lokální konfigurace spojovacího modelu v adminu."""

    def test_model_is_registered_with_exact_configuration(self) -> None:
        self.assertTrue(admin.site.is_registered(PersonGraveSite))
        model_admin = admin.site._registry[PersonGraveSite]

        self.assertIsInstance(model_admin, PersonGraveSiteAdmin)
        self.assertEqual(
            model_admin.list_display,
            (
                "person",
                "grave_site",
                "role",
                "access_level",
                "verification_status",
                "archived_at",
                "deleted_at",
            ),
        )
        self.assertEqual(
            model_admin.list_filter,
            (
                "role",
                "access_level",
                "verification_status",
                "archived_at",
                "deleted_at",
            ),
        )
        self.assertEqual(
            model_admin.search_fields,
            (
                "person__first_name",
                "person__last_name",
                "grave_site__cemetery_name",
                "grave_site__location_text",
                "grave_site__grave_number",
                "role__name",
                "note",
            ),
        )
        self.assertEqual(
            model_admin.list_select_related,
            ("person", "grave_site", "role"),
        )
