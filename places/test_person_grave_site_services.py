from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from events.models import Event
from people.models import Person

from . import services
from .choices import GraveSiteStatus
from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
)
from .services import (
    PersonGraveSiteInput,
    create_person_grave_site,
    update_person_grave_site,
)


class PersonGraveSiteServiceApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu služeb propojení osoby a místa."""

    def test_module_exports_exact_approved_api(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "GraveSiteInput",
                "PersonGraveSiteInput",
                "ResidenceInput",
                "create_grave_site",
                "create_person_grave_site",
                "create_residence",
                "update_grave_site",
                "update_person_grave_site",
                "update_residence",
            ),
        )

    def test_input_is_frozen_slotted_dataclass(self) -> None:
        data = PersonGraveSiteInput(
            person=Person(),
            grave_site=GraveSite(),
            role=PersonGraveSiteRole(),
        )

        self.assertFalse(hasattr(data, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            data.note = "Změna"

    def test_input_has_exact_fields_in_order(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(PersonGraveSiteInput)),
            (
                "person",
                "grave_site",
                "role",
                "note",
                "access_level",
                "verification_status",
            ),
        )

    def test_input_defaults_match_contract(self) -> None:
        data = PersonGraveSiteInput(
            person=Person(),
            grave_site=GraveSite(),
            role=PersonGraveSiteRole(),
        )

        self.assertEqual(data.note, "")
        self.assertEqual(data.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            data.verification_status,
            VerificationStatus.UNCONFIRMED,
        )

    def test_service_signatures_are_keyword_only_with_return_type(
        self,
    ) -> None:
        expectations = (
            (
                create_person_grave_site,
                ("data", "created_by"),
            ),
            (
                update_person_grave_site,
                ("link", "data"),
            ),
        )
        for service, parameter_names in expectations:
            with self.subTest(service=service.__name__):
                service_signature = signature(service)
                self.assertEqual(
                    tuple(service_signature.parameters),
                    parameter_names,
                )
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in service_signature.parameters.values()
                    )
                )
                self.assertIs(
                    service_signature.return_annotation,
                    PersonGraveSite,
                )


class PersonGraveSiteServiceTests(TestCase):
    """Integrační testy vytvoření a změny propojení osoby a místa."""

    def setUp(self) -> None:
        self.person = self.make_person("Anna", "První")
        self.other_person = self.make_person("Bohumil", "Druhý")
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.other_grave_site_type = GraveSiteType.objects.get(
            code="memorial"
        )
        self.grave_site = self.make_grave_site(
            self.grave_site_type,
            "První místo",
        )
        self.other_grave_site = self.make_grave_site(
            self.other_grave_site_type,
            "Druhé místo",
        )
        self.role = PersonGraveSiteRole.objects.get(code="buried")
        self.other_role = PersonGraveSiteRole.objects.get(
            code="commemorated"
        )

    @staticmethod
    def make_person(first_name: str, last_name: str) -> Person:
        return Person.objects.create(
            first_name=first_name,
            last_name=last_name,
        )

    @staticmethod
    def make_grave_site(
        grave_site_type: GraveSiteType,
        location_text: str,
    ) -> GraveSite:
        return GraveSite.objects.create(
            grave_site_type=grave_site_type,
            location_text=location_text,
        )

    @staticmethod
    def make_role(
        code: str,
        *,
        is_active: bool = True,
    ) -> PersonGraveSiteRole:
        return PersonGraveSiteRole.objects.create(
            code=code,
            name=code,
            is_active=is_active,
        )

    def make_data(self, **changes: object) -> PersonGraveSiteInput:
        data = PersonGraveSiteInput(
            person=self.person,
            grave_site=self.grave_site,
            role=self.role,
        )
        return replace(data, **changes)

    def create_base_link(self, **changes: object) -> PersonGraveSite:
        return create_person_grave_site(data=self.make_data(**changes))

    @staticmethod
    def assert_error(
        context,
        *,
        key: str,
        code: str,
    ) -> None:
        errors = context.exception.error_dict
        if key not in errors:
            raise AssertionError(f"Chybí očekávaný klíč {key!r}: {errors}")
        codes = [error.code for error in errors[key]]
        if code not in codes:
            raise AssertionError(
                f"Chybí očekávaný kód {code!r} v {key!r}: {codes}"
            )

    def test_create_accepts_all_system_roles_and_active_user_role(
        self,
    ) -> None:
        role_codes = (
            "buried",
            "urn_placed",
            "ashes_scattered",
            "commemorated",
            "remains_relocated_from",
            "remains_relocated_to",
        )
        roles = [
            PersonGraveSiteRole.objects.get(code=code)
            for code in role_codes
        ]
        roles.append(self.make_role("service_user_role"))

        for role in roles:
            with self.subTest(role=role.code):
                result = create_person_grave_site(
                    data=self.make_data(role=role)
                )
                self.assertEqual(result.role_id, role.pk)

        self.assertEqual(PersonGraveSite.objects.count(), len(roles))

    def test_create_stores_all_values_and_created_by(self) -> None:
        creator = get_user_model().objects.create_user(
            username="person-grave-site-creator"
        )
        data = self.make_data(
            person=self.other_person,
            grave_site=self.other_grave_site,
            role=self.other_role,
            note="Doložené propojení",
            access_level=AccessLevel.RESTRICTED,
            verification_status=VerificationStatus.VERIFIED,
        )

        result = create_person_grave_site(
            data=data,
            created_by=creator,
        )

        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.grave_site_id, self.other_grave_site.pk)
        self.assertEqual(result.role_id, self.other_role.pk)
        self.assertEqual(result.note, "Doložené propojení")
        self.assertEqual(result.access_level, AccessLevel.RESTRICTED)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.VERIFIED,
        )
        self.assertEqual(result.created_by_id, creator.pk)

    def test_create_uses_defaults_and_returns_fresh_instance(self) -> None:
        result = self.create_base_link()

        self.assertFalse(result._state.adding)
        self.assertEqual(result.note, "")
        self.assertEqual(result.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            result.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertIsNone(result.created_by_id)
        self.assertIsNone(result.archived_at)
        self.assertIsNone(result.deleted_at)
        self.assertEqual(
            set(result._state.fields_cache),
            {"person", "grave_site", "role", "created_by"},
        )

    def test_service_strips_note_and_preserves_internal_spacing(
        self,
    ) -> None:
        result = create_person_grave_site(
            data=self.make_data(note="  Historická   poznámka  ")
        )
        whitespace = create_person_grave_site(
            data=self.make_data(note=" \t ")
        )

        self.assertEqual(result.note, "Historická   poznámka")
        self.assertEqual(whitespace.note, "")

    def test_model_save_outside_service_does_not_strip_note(self) -> None:
        link = PersonGraveSite.objects.create(
            person=self.person,
            grave_site=self.grave_site,
            role=self.role,
            note="  Beze změny  ",
        )
        link.refresh_from_db()

        self.assertEqual(link.note, "  Beze změny  ")

    def test_access_and_verification_defaults_and_explicit_values(
        self,
    ) -> None:
        default = self.create_base_link()
        explicit = create_person_grave_site(
            data=self.make_data(
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.DISPUTED,
            )
        )

        self.assertEqual(default.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            default.verification_status,
            VerificationStatus.UNCONFIRMED,
        )
        self.assertEqual(explicit.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            explicit.verification_status,
            VerificationStatus.DISPUTED,
        )

    def test_invalid_access_or_verification_rolls_back(self) -> None:
        for field_name in ("access_level", "verification_status"):
            with self.subTest(create_field=field_name):
                with self.assertRaises(ValidationError) as context:
                    create_person_grave_site(
                        data=self.make_data(
                            **{field_name: "invalid"}
                        )
                    )
                self.assert_error(
                    context,
                    key=field_name,
                    code="invalid_choice",
                )
        self.assertEqual(PersonGraveSite.objects.count(), 0)

        link = self.create_base_link(note="Původní")
        original_updated_at = link.updated_at
        for field_name in ("access_level", "verification_status"):
            with self.subTest(update_field=field_name):
                with self.assertRaises(ValidationError) as context:
                    update_person_grave_site(
                        link=link,
                        data=self.make_data(
                            note="Změněno",
                            **{field_name: "invalid"},
                        ),
                    )
                self.assert_error(
                    context,
                    key=field_name,
                    code="invalid_choice",
                )
                link.refresh_from_db()
                self.assertEqual(link.note, "Původní")
                self.assertEqual(link.updated_at, original_updated_at)

    def test_rejects_unsaved_and_physically_missing_person(self) -> None:
        unsaved = Person(first_name="Neuložená")
        missing = self.make_person("Odstraněná", "Osoba")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for person in (unsaved, missing):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    create_person_grave_site(
                        data=self.make_data(person=person)
                    )
                self.assert_error(
                    context,
                    key="person",
                    code="person_grave_site_person_unsaved",
                )

    def test_rejects_unsaved_and_physically_missing_grave_site(
        self,
    ) -> None:
        unsaved = GraveSite(
            grave_site_type=self.grave_site_type,
            location_text="Neuložené",
        )
        missing = self.make_grave_site(
            self.grave_site_type,
            "Odstraněné",
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for grave_site in (unsaved, missing):
            with self.subTest(grave_site=grave_site.location_text):
                with self.assertRaises(ValidationError) as context:
                    create_person_grave_site(
                        data=self.make_data(grave_site=grave_site)
                    )
                self.assert_error(
                    context,
                    key="grave_site",
                    code="person_grave_site_grave_site_unsaved",
                )

    def test_rejects_unsaved_and_physically_missing_role(self) -> None:
        unsaved = PersonGraveSiteRole(
            code="unsaved_role",
            name="Neuložená role",
        )
        missing = self.make_role("missing_role")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for role in (unsaved, missing):
            with self.subTest(role=role.code):
                with self.assertRaises(ValidationError) as context:
                    create_person_grave_site(
                        data=self.make_data(role=role)
                    )
                self.assert_error(
                    context,
                    key="role",
                    code="person_grave_site_role_unsaved",
                )

    def test_rejects_unsaved_and_physically_missing_created_by(
        self,
    ) -> None:
        user_model = get_user_model()
        unsaved = user_model(username="unsaved-link-author")
        missing = user_model.objects.create_user(
            username="missing-link-author"
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for creator in (unsaved, missing):
            with self.subTest(username=creator.username):
                with self.assertRaises(ValidationError) as context:
                    create_person_grave_site(
                        data=self.make_data(),
                        created_by=creator,
                    )
                self.assert_error(
                    context,
                    key="created_by",
                    code="person_grave_site_created_by_unsaved",
                )

    def test_create_uses_fresh_inactive_role_state(self) -> None:
        PersonGraveSiteRole.objects.filter(pk=self.role.pk).update(
            is_active=False
        )
        self.assertTrue(self.role.is_active)

        with self.assertRaises(ValidationError) as context:
            self.create_base_link()

        self.assert_error(
            context,
            key="role",
            code="person_grave_site_role_inactive",
        )
        self.assertEqual(PersonGraveSite.objects.count(), 0)

    def test_update_keeps_same_inactive_role_by_primary_key(self) -> None:
        inactive = self.make_role("inactive_same", is_active=False)
        link = PersonGraveSite.objects.create(
            person=self.person,
            grave_site=self.grave_site,
            role=inactive,
        )
        stale_same_pk = PersonGraveSiteRole(
            pk=inactive.pk,
            code=inactive.code,
            name=inactive.name,
            is_active=True,
        )

        result = update_person_grave_site(
            link=link,
            data=self.make_data(
                role=stale_same_pk,
                note="Doplněno",
            ),
        )

        self.assertEqual(result.role_id, inactive.pk)
        self.assertEqual(result.note, "Doplněno")

    def test_update_rejects_transition_to_other_inactive_role(
        self,
    ) -> None:
        inactive_current = self.make_role(
            "inactive_current",
            is_active=False,
        )
        inactive_target = self.make_role(
            "inactive_target",
            is_active=False,
        )
        active_link = self.create_base_link()
        inactive_link = PersonGraveSite.objects.create(
            person=self.person,
            grave_site=self.grave_site,
            role=inactive_current,
        )

        for link in (active_link, inactive_link):
            with self.subTest(link=link.pk):
                with self.assertRaises(ValidationError) as context:
                    update_person_grave_site(
                        link=link,
                        data=self.make_data(role=inactive_target),
                    )
                self.assert_error(
                    context,
                    key="role",
                    code="person_grave_site_role_inactive",
                )

    def test_update_allows_inactive_to_active_role(self) -> None:
        inactive = self.make_role("inactive_old", is_active=False)
        link = PersonGraveSite.objects.create(
            person=self.person,
            grave_site=self.grave_site,
            role=inactive,
        )

        result = update_person_grave_site(
            link=link,
            data=self.make_data(role=self.other_role),
        )

        self.assertEqual(result.role_id, self.other_role.pk)

    def test_update_uses_fresh_current_role_for_transition(self) -> None:
        inactive = self.make_role("fresh_inactive", is_active=False)
        link = self.create_base_link()
        PersonGraveSite.objects.filter(pk=link.pk).update(role=inactive)
        self.assertEqual(link.role_id, self.role.pk)

        result = update_person_grave_site(
            link=link,
            data=self.make_data(role=inactive, note="Povoleno"),
        )

        self.assertEqual(result.role_id, inactive.pk)
        self.assertEqual(result.note, "Povoleno")

    def test_update_replaces_complete_editable_snapshot(self) -> None:
        link = self.create_base_link()

        result = update_person_grave_site(
            link=link,
            data=self.make_data(
                person=self.other_person,
                grave_site=self.other_grave_site,
                role=self.other_role,
                note="Nová poznámka",
                access_level=AccessLevel.AUTHENTICATED,
                verification_status=VerificationStatus.PROBABLE,
            ),
        )

        self.assertEqual(result.person_id, self.other_person.pk)
        self.assertEqual(result.grave_site_id, self.other_grave_site.pk)
        self.assertEqual(result.role_id, self.other_role.pk)
        self.assertEqual(result.note, "Nová poznámka")
        self.assertEqual(
            result.access_level,
            AccessLevel.AUTHENTICATED,
        )
        self.assertEqual(
            result.verification_status,
            VerificationStatus.PROBABLE,
        )

    def test_update_preserves_fresh_author_and_lifecycle_metadata(
        self,
    ) -> None:
        original_creator = get_user_model().objects.create_user(
            username="original-link-creator"
        )
        current_creator = get_user_model().objects.create_user(
            username="current-link-creator"
        )
        archivist = get_user_model().objects.create_user(
            username="link-archivist"
        )
        link = create_person_grave_site(
            data=self.make_data(),
            created_by=original_creator,
        )
        created_at = link.created_at
        archived_at = timezone.now() - timedelta(days=1)
        old_updated_at = link.updated_at - timedelta(days=1)
        PersonGraveSite.objects.filter(pk=link.pk).update(
            created_by=current_creator,
            archived_at=archived_at,
            archived_by=archivist,
            archive_reason="Historický záznam",
            updated_at=old_updated_at,
        )

        result = update_person_grave_site(
            link=link,
            data=self.make_data(note="Upraveno"),
        )

        self.assertEqual(result.created_by_id, current_creator.pk)
        self.assertEqual(result.created_at, created_at)
        self.assertEqual(result.archived_at, archived_at)
        self.assertEqual(result.archived_by_id, archivist.pk)
        self.assertEqual(result.archive_reason, "Historický záznam")
        self.assertIsNone(result.deleted_at)
        self.assertIsNone(result.deleted_by_id)
        self.assertEqual(result.deletion_reason, "")
        self.assertGreater(result.updated_at, old_updated_at)

    def test_update_rejects_fresh_soft_deleted_link(self) -> None:
        link = self.create_base_link(note="Původní")
        deleted_at = timezone.now()
        PersonGraveSite.objects.filter(pk=link.pk).update(
            deleted_at=deleted_at
        )
        self.assertIsNone(link.deleted_at)

        with self.assertRaises(ValidationError) as context:
            update_person_grave_site(
                link=link,
                data=self.make_data(note="Změněno"),
            )

        self.assert_error(
            context,
            key="link",
            code="person_grave_site_deleted",
        )
        link.refresh_from_db()
        self.assertEqual(link.note, "Původní")
        self.assertEqual(link.deleted_at, deleted_at)

    def test_update_rejects_unsaved_and_physically_missing_link(
        self,
    ) -> None:
        unsaved = PersonGraveSite()
        missing = self.create_base_link()
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for link in (unsaved, missing):
            with self.subTest(link=link.pk):
                with self.assertRaises(ValidationError) as context:
                    update_person_grave_site(
                        link=link,
                        data=self.make_data(),
                    )
                self.assert_error(
                    context,
                    key="link",
                    code="person_grave_site_unsaved",
                )

    def test_archived_and_soft_deleted_people_are_allowed(self) -> None:
        archived = self.make_person("Archivovaná", "Osoba")
        deleted = self.make_person("Měkce", "Odstraněná")
        now = timezone.now()
        Person.objects.filter(pk=archived.pk).update(archived_at=now)
        Person.objects.filter(pk=deleted.pk).update(deleted_at=now)

        archived_result = create_person_grave_site(
            data=self.make_data(person=archived)
        )
        deleted_result = create_person_grave_site(
            data=self.make_data(person=deleted)
        )

        self.assertEqual(archived_result.person_id, archived.pk)
        self.assertEqual(deleted_result.person_id, deleted.pk)

    def test_archived_soft_deleted_and_destroyed_sites_are_allowed(
        self,
    ) -> None:
        archived = self.make_grave_site(
            self.grave_site_type,
            "Archivované místo",
        )
        deleted = self.make_grave_site(
            self.grave_site_type,
            "Měkce odstraněné místo",
        )
        destroyed = self.make_grave_site(
            self.grave_site_type,
            "Zaniklé místo",
        )
        now = timezone.now()
        GraveSite.objects.filter(pk=archived.pk).update(archived_at=now)
        GraveSite.objects.filter(pk=deleted.pk).update(deleted_at=now)
        GraveSite.objects.filter(pk=destroyed.pk).update(
            status=GraveSiteStatus.DESTROYED
        )

        for grave_site in (archived, deleted, destroyed):
            with self.subTest(grave_site=grave_site.pk):
                result = create_person_grave_site(
                    data=self.make_data(grave_site=grave_site)
                )
                self.assertEqual(result.grave_site_id, grave_site.pk)

    def test_unusual_role_and_site_type_combination_is_allowed(self) -> None:
        result = create_person_grave_site(
            data=self.make_data(
                grave_site=self.other_grave_site,
                role=self.role,
            )
        )

        self.assertEqual(
            result.grave_site.grave_site_type_id,
            self.other_grave_site_type.pk,
        )
        self.assertEqual(result.role.code, "buried")

    def test_service_allows_duplicate_links(self) -> None:
        first = self.create_base_link()
        second = self.create_base_link()

        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(PersonGraveSite.objects.count(), 2)

    def test_service_allows_multiple_people_sites_and_roles(self) -> None:
        first = self.create_base_link()
        second = create_person_grave_site(
            data=self.make_data(person=self.other_person)
        )
        third = create_person_grave_site(
            data=self.make_data(grave_site=self.other_grave_site)
        )
        fourth = create_person_grave_site(
            data=self.make_data(role=self.other_role)
        )

        self.assertEqual(self.grave_site.person_links.count(), 3)
        self.assertEqual(self.person.grave_site_links.count(), 3)
        self.assertEqual(
            {first.role_id, fourth.role_id},
            {self.role.pk, self.other_role.pk},
        )
        self.assertEqual(second.person_id, self.other_person.pk)
        self.assertEqual(third.grave_site_id, self.other_grave_site.pk)

    def test_create_uses_fresh_person_and_grave_site_state(self) -> None:
        Person.objects.filter(pk=self.person.pk).update(
            first_name="Aktuální"
        )
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            status=GraveSiteStatus.DESTROYED
        )
        self.assertEqual(self.person.first_name, "Anna")
        self.assertEqual(self.grave_site.status, GraveSiteStatus.UNKNOWN)

        result = self.create_base_link()

        self.assertEqual(result.person.first_name, "Aktuální")
        self.assertEqual(
            result.grave_site.status,
            GraveSiteStatus.DESTROYED,
        )

    def test_invalid_update_rolls_back_every_changed_field(self) -> None:
        creator = get_user_model().objects.create_user(
            username="rollback-link-creator"
        )
        link = create_person_grave_site(
            data=self.make_data(note="Původní"),
            created_by=creator,
        )
        original_values = {
            field_name: getattr(link, field_name)
            for field_name in (
                "person_id",
                "grave_site_id",
                "role_id",
                "note",
                "access_level",
                "verification_status",
                "created_by_id",
                "created_at",
                "updated_at",
                "archived_at",
                "deleted_at",
            )
        }

        with self.assertRaises(ValidationError):
            update_person_grave_site(
                link=link,
                data=self.make_data(
                    person=self.other_person,
                    grave_site=self.other_grave_site,
                    role=self.other_role,
                    note="Nová poznámka",
                    access_level="invalid",
                    verification_status=VerificationStatus.VERIFIED,
                ),
            )

        link.refresh_from_db()
        self.assertEqual(
            {
                field_name: getattr(link, field_name)
                for field_name in original_values
            },
            original_values,
        )

    def test_service_has_no_unplanned_side_writes(self) -> None:
        person_values = (
            self.person.first_name,
            self.person.last_name,
            self.person.archived_at,
            self.person.deleted_at,
        )
        site_values = (
            self.grave_site.status,
            self.grave_site.archived_at,
            self.grave_site.deleted_at,
        )
        role_values = (
            self.role.code,
            self.role.name,
            self.role.is_active,
        )
        event_count = Event.objects.count()

        self.create_base_link(note="Bez vedlejších zápisů")

        self.person.refresh_from_db()
        self.grave_site.refresh_from_db()
        self.role.refresh_from_db()
        self.assertEqual(
            (
                self.person.first_name,
                self.person.last_name,
                self.person.archived_at,
                self.person.deleted_at,
            ),
            person_values,
        )
        self.assertEqual(
            (
                self.grave_site.status,
                self.grave_site.archived_at,
                self.grave_site.deleted_at,
            ),
            site_values,
        )
        self.assertEqual(
            (self.role.code, self.role.name, self.role.is_active),
            role_values,
        )
        self.assertEqual(Event.objects.count(), event_count)
        self.assertEqual(PersonGraveSite.objects.count(), 1)

    def test_update_uses_select_for_update_on_link(self) -> None:
        link = self.create_base_link()

        with patch.object(
            PersonGraveSite.objects,
            "select_for_update",
            wraps=PersonGraveSite.objects.select_for_update,
        ) as mocked_lock:
            update_person_grave_site(
                link=link,
                data=self.make_data(note="Zamčeno"),
            )

        mocked_lock.assert_called_once_with()

    def test_unexpected_integrity_error_is_not_mapped(self) -> None:
        with patch.object(
            PersonGraveSite,
            "save",
            side_effect=IntegrityError("neočekávaná chyba"),
        ):
            with self.assertRaises(IntegrityError):
                self.create_base_link()

        self.assertEqual(PersonGraveSite.objects.count(), 0)
