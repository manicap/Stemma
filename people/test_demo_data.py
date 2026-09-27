from dataclasses import FrozenInstanceError, fields
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from common.choices import AccessLevel, Gender, VerificationStatus
from events.models import Event, EventParticipant, EventType
from health import use_cases as health_use_cases
from health.models import HealthRecord
from materials.models import (
    Attachment,
    HealthRecordAttachment,
    HealthRecordSource,
    Source,
)

from . import services
from .models import Person, PersonCategory
from .services import BasicPersonInput, PersonInput, create_person


class PersonServiceApiTests(SimpleTestCase):
    def test_public_api_includes_person_and_relationship_services(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "BasicPersonInput",
                "PersonInput",
                "RelationshipInput",
                "create_person",
                "create_relationship",
                "update_person",
                "update_person_basic",
                "update_relationship",
            ),
        )

    def test_person_input_is_frozen_slotted_and_has_stable_fields(self) -> None:
        data = PersonInput()

        self.assertFalse(hasattr(data, "__dict__"))
        self.assertEqual(
            tuple(field.name for field in fields(PersonInput)),
            (
                "category",
                "gender",
                "first_name",
                "last_name",
                "title_before_name",
                "title_after_name",
                "notes",
                "biography",
                "access_level",
                "verification_status",
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            data.first_name = "Změna"

    def test_basic_person_input_is_frozen_slotted_and_scoped(self) -> None:
        data = BasicPersonInput()

        self.assertFalse(hasattr(data, "__dict__"))
        self.assertEqual(
            tuple(field.name for field in fields(BasicPersonInput)),
            ("category", "gender", "first_name", "last_name", "notes"),
        )
        with self.assertRaises(FrozenInstanceError):
            data.first_name = "Změna"


class PersonServiceTests(TestCase):
    def test_create_person_normalizes_and_validates_input(self) -> None:
        actor = get_user_model().objects.create_user(username="creator")
        category = PersonCategory.objects.get(code="direct_family")

        person = create_person(
            data=PersonInput(
                category=category,
                gender=Gender.FEMALE,
                first_name="  Anna ",
                last_name=" Nováková  ",
                title_before_name="  PhDr. ",
                title_after_name=" Ph.D.  ",
                notes=" Poznámka. ",
                biography=" Životopisný text. ",
                access_level=AccessLevel.AUTHENTICATED,
                verification_status=VerificationStatus.VERIFIED,
            ),
            created_by=actor,
        )

        self.assertEqual(person.first_name, "Anna")
        self.assertEqual(person.last_name, "Nováková")
        self.assertEqual(person.title_before_name, "PhDr.")
        self.assertEqual(person.title_after_name, "Ph.D.")
        self.assertEqual(person.notes, "Poznámka.")
        self.assertEqual(person.biography, "Životopisný text.")
        self.assertEqual(person.category, category)
        self.assertEqual(person.created_by, actor)

    def test_create_person_rejects_empty_identity_without_write(self) -> None:
        with self.assertRaises(ValidationError):
            create_person(data=PersonInput())

        self.assertFalse(Person.objects.exists())


@override_settings(DEBUG=True)
class SeedDemoDataCommandTests(TestCase):
    def run_command(self, *args: str) -> str:
        output = StringIO()
        call_command("seed_demo_data", *args, stdout=output)
        return output.getvalue()

    def test_command_creates_synthetic_visibility_examples(self) -> None:
        output = self.run_command()

        self.assertIn("osoby nové 5", output)
        self.assertIn("události nové 3", output)
        self.assertIn("health ukázky nové 1", output)
        self.assertEqual(Person.objects.count(), 5)
        self.assertEqual(
            set(Person.objects.values_list("access_level", flat=True)),
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.RESTRICTED,
            },
        )
        self.assertEqual(Event.objects.count(), 3)
        self.assertEqual(EventParticipant.objects.count(), 3)
        self.assertEqual(HealthRecord.objects.count(), 1)
        self.assertEqual(Attachment.objects.count(), 1)
        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(HealthRecordAttachment.objects.count(), 1)
        self.assertEqual(HealthRecordSource.objects.count(), 1)
        seed_actor = get_user_model().objects.get(
            username="stemma-demo-health-writer"
        )
        self.assertFalse(seed_actor.has_usable_password())
        self.assertTrue(seed_actor.is_active)
        self.assertFalse(seed_actor.is_staff)
        self.assertFalse(seed_actor.is_superuser)
        self.assertEqual(
            HealthRecord.objects.get().created_by_id,
            seed_actor.pk,
        )
        self.assertEqual(
            set(
                EventParticipant.objects.values_list(
                    "event__event_type__code",
                    "role__code",
                )
            ),
            {
                ("birth", "born_person"),
                ("death", "deceased_person"),
            },
        )

    @override_settings(DEBUG=False)
    def test_command_fails_closed_outside_local_debug_mode(self) -> None:
        with self.assertRaisesMessage(
            CommandError,
            "pouze v lokálním režimu DEBUG",
        ):
            self.run_command()

        self.assertFalse(Person.objects.exists())

    def test_command_is_idempotent_and_does_not_overwrite_demo_record(self) -> None:
        self.run_command()
        person = Person.objects.get(notes__contains="stemma-demo:public")
        person.first_name = "Uživatelská změna"
        person.notes = f"{person.notes} Uživatelský dodatek."
        person.save(update_fields=("first_name", "notes"))

        output = self.run_command()

        self.assertIn("osoby nové 0", output)
        self.assertIn("osoby existující 5", output)
        self.assertIn("události nové 0", output)
        self.assertIn("události existující 3", output)
        self.assertIn("health ukázky nové 0", output)
        self.assertIn("health ukázky existující 1", output)
        self.assertEqual(Person.objects.count(), 5)
        self.assertEqual(Event.objects.count(), 3)
        self.assertEqual(HealthRecord.objects.count(), 1)
        self.assertEqual(HealthRecordAttachment.objects.count(), 1)
        self.assertEqual(HealthRecordSource.objects.count(), 1)
        self.assertEqual(
            get_user_model().objects.filter(
                username="stemma-demo-health-writer"
            ).count(),
            1,
        )
        person.refresh_from_db()
        self.assertEqual(person.first_name, "Uživatelská změna")
        self.assertTrue(person.notes.endswith("Uživatelský dodatek."))

    def test_command_completes_partially_seeded_data(self) -> None:
        create_person(
            data=PersonInput(
                first_name="Vlastní veřejná ukázka",
                notes="Zachovat. [stemma-demo:public]",
            )
        )

        output = self.run_command()

        self.assertIn("osoby nové 4", output)
        self.assertIn("osoby existující 1", output)
        self.assertEqual(Person.objects.count(), 5)
        self.assertEqual(Event.objects.count(), 3)

    def test_command_rolls_back_the_batch_when_later_creation_fails(
        self,
    ) -> None:
        original_create_person = create_person
        call_count = 0

        def fail_second_creation(*, data, created_by=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise ValidationError("Simulované selhání dávky.")
            return original_create_person(data=data, created_by=created_by)

        with patch(
            "people.management.commands.seed_demo_data.create_person",
            side_effect=fail_second_creation,
        ):
            with self.assertRaises(ValidationError):
                self.run_command()

        self.assertFalse(Person.objects.exists())

    def test_dry_run_describes_plan_without_writes(self) -> None:
        output = self.run_command("--dry-run")

        self.assertIn("Plán: osoby nové 5", output)
        self.assertIn("události nové 3", output)
        self.assertIn("health ukázky nové 1", output)
        self.assertFalse(Person.objects.exists())
        self.assertFalse(Event.objects.exists())
        self.assertFalse(HealthRecord.objects.exists())
        self.assertFalse(Attachment.objects.exists())
        self.assertFalse(Source.objects.exists())

    def test_missing_life_event_catalog_rolls_back_people(self) -> None:
        EventType.objects.filter(code="birth").update(code="missing-birth")

        with self.assertRaisesMessage(CommandError, "spusťte migrace"):
            self.run_command()

        self.assertFalse(Person.objects.exists())
        self.assertFalse(Event.objects.exists())

    def test_seeded_life_facts_are_visible_in_real_detail_flow(self) -> None:
        self.run_command()
        older = Person.objects.get(
            notes__contains="stemma-demo:derived:older"
        )

        response = self.client.get(f"/osoby/{older.pk}/")

        self.assertContains(response, "Josef Dvořák I.", count=2)
        self.assertContains(response, "Narození:</strong> 1. 1. 1900")
        self.assertContains(response, "Úmrtí:</strong> 1. 1. 1980")
        self.assertContains(response, "80 let")

    def test_seeded_health_data_is_visible_in_real_read_only_flow(self) -> None:
        self.run_command()
        person = Person.objects.get(notes__contains="stemma-demo:restricted")
        actor = get_user_model().objects.create_user(username="health-reader")
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                codename="view_restricted_content",
            )
        )
        self.client.force_login(actor)

        list_response = self.client.get(
            reverse("people:health", args=(person.pk,))
        )
        health_record = HealthRecord.objects.get(person=person)
        detail_response = self.client.get(
            reverse(
                "people:health-record-detail",
                args=(person.pk, health_record.pk),
            )
        )

        self.assertContains(list_response, "Preventivní prohlídka")
        self.assertContains(detail_response, "Ukázková zpráva z prohlídky")
        self.assertContains(detail_response, "Ukázková karta pacienta")
        self.assertNotContains(
            detail_response,
            "stemma-demo/health/preventive-checkup.pdf",
        )

    def test_health_business_writes_use_actor_aware_use_cases(self) -> None:
        with (
            patch(
                "people.management.commands.seed_demo_data.create_health_record",
                wraps=health_use_cases.create_health_record,
            ) as create_record,
            patch(
                "people.management.commands.seed_demo_data."
                "create_health_record_attachment",
                wraps=health_use_cases.create_health_record_attachment,
            ) as create_attachment_link,
            patch(
                "people.management.commands.seed_demo_data."
                "create_health_record_source",
                wraps=health_use_cases.create_health_record_source,
            ) as create_source_link,
        ):
            self.run_command()

        create_record.assert_called_once()
        create_attachment_link.assert_called_once()
        create_source_link.assert_called_once()
        seed_actor = get_user_model().objects.get(
            username="stemma-demo-health-writer"
        )
        self.assertFalse(seed_actor.has_usable_password())
        self.assertEqual(
            set(seed_actor.get_all_permissions()),
            {
                "accounts.view_restricted_content",
                "health.add_healthrecord",
                "materials.add_healthrecordattachment",
                "materials.add_healthrecordsource",
            },
        )

    def test_health_seed_actor_rejects_extra_direct_permission(self) -> None:
        seed_actor = get_user_model().objects.create_user(
            username="stemma-demo-health-writer"
        )
        seed_actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )

        with self.assertRaisesMessage(CommandError, "neočekávaná oprávnění"):
            self.run_command()

        self.assertFalse(HealthRecord.objects.exists())

    def test_health_seed_actor_rejects_group_membership(self) -> None:
        seed_actor = get_user_model().objects.create_user(
            username="stemma-demo-health-writer"
        )
        seed_actor.groups.add(Group.objects.create(name="Unexpected seed role"))

        with self.assertRaisesMessage(CommandError, "neočekávaná oprávnění"):
            self.run_command()

        self.assertFalse(HealthRecord.objects.exists())
