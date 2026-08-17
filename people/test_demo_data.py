from dataclasses import FrozenInstanceError, fields
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from common.choices import AccessLevel, Gender, VerificationStatus
from events.models import Event, EventParticipant, EventType

from . import services
from .models import Person, PersonCategory
from .services import PersonInput, create_person


class PersonServiceApiTests(SimpleTestCase):
    def test_public_api_includes_person_and_relationship_services(self) -> None:
        self.assertEqual(
            services.__all__,
            (
                "PersonInput",
                "RelationshipInput",
                "create_person",
                "create_relationship",
                "update_person",
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
                "notes",
                "access_level",
                "verification_status",
            ),
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
                notes=" Poznámka. ",
                access_level=AccessLevel.AUTHENTICATED,
                verification_status=VerificationStatus.VERIFIED,
            ),
            created_by=actor,
        )

        self.assertEqual(person.first_name, "Anna")
        self.assertEqual(person.last_name, "Nováková")
        self.assertEqual(person.notes, "Poznámka.")
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
        self.assertEqual(Person.objects.count(), 5)
        self.assertEqual(Event.objects.count(), 3)
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
        self.assertFalse(Person.objects.exists())
        self.assertFalse(Event.objects.exists())

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
