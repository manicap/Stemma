from dataclasses import replace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from events.models import Event, EventParticipant, EventType, ParticipantRole
from events.services import EventInput
from events.use_cases import create_person_life_event
from places.models import Place

from .models import Person


class PersonLifeEventWriteWebTests(TestCase):
    """Security and HTTP integration for the narrow birth/death editor."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.birth_type = EventType.objects.get(code="birth")
        cls.death_type = EventType.objects.get(code="death")
        cls.born_role = ParticipantRole.objects.get(code="born_person")
        cls.deceased_role = ParticipantRole.objects.get(
            code="deceased_person"
        )
        cls.witness_role = ParticipantRole.objects.get(code="witness")
        cls.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            access_level=AccessLevel.PUBLIC,
        )
        cls.witness = Person.objects.create(
            first_name="Jan",
            last_name="Svědek",
            access_level=AccessLevel.PUBLIC,
        )

    def editor(self, username: str = "life-event-editor"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Editor"))
        return actor

    def reader(self, username: str = "life-event-reader"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Čtenář"))
        return actor

    def form_data(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "date_precision": DatePrecision.YEAR,
            "date_qualifier": DateQualifier.NONE,
            "start_year": 1890,
            "start_month": "",
            "start_day": "",
            "original_date_text": "",
            "date_note": "",
            "place": "",
            "location_detail": "",
            "title": "",
            "description": "Zápis z matriky",
            "access_level": AccessLevel.PUBLIC,
            "verification_status": VerificationStatus.UNCONFIRMED,
        }
        values.update(overrides)
        return values

    def create_event(
        self,
        *,
        event_type: EventType,
        role: ParticipantRole,
        access_level: str = AccessLevel.PUBLIC,
        year: int = 1890,
    ) -> Event:
        event = Event.objects.create(
            event_type=event_type,
            access_level=access_level,
            date_precision=DatePrecision.YEAR,
            start_year=year,
        )
        EventParticipant.objects.create(
            event=event,
            person=self.person,
            role=role,
        )
        return event

    def test_editor_permissions_and_htmx_birth_creation_refresh_all_surfaces(
        self,
    ) -> None:
        actor = self.editor()
        self.assertTrue(actor.has_perm("events.add_event"))
        self.assertTrue(actor.has_perm("events.change_event"))
        self.client.force_login(actor)

        response = self.client.post(
            reverse("people:birth-create", args=(self.person.pk,))
            + "?q=anna&sort=oldest",
            self.form_data(
                date_qualifier=DateQualifier.APPROXIMATE,
                start_year=1885,
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(event_type=self.birth_type)
        self.assertEqual(event.start_year, 1885)
        self.assertEqual(event.created_by, actor)
        self.assertTrue(
            EventParticipant.objects.filter(
                event=event,
                person=self.person,
                role=self.born_role,
            ).exists()
        )
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:events", args=(self.person.pk,))
            + "?q=anna&sort=oldest",
        )
        self.assertContains(response, "Narození:")
        self.assertContains(response, "přibližně 1885")
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertContains(response, "Upravit narození")

    def test_death_creation_full_page_redirect_and_private_non_leak(
        self,
    ) -> None:
        actor = self.editor("death-editor")
        self.client.force_login(actor)
        response = self.client.post(
            reverse("people:death-create", args=(self.person.pk,))
            + "?category=&sort=last_name_asc",
            self.form_data(
                date_precision=DatePrecision.MONTH,
                start_year=1975,
                start_month=4,
                access_level=AccessLevel.AUTHENTICATED,
            ),
        )

        event = Event.objects.get(event_type=self.death_type)
        self.assertEqual(event.start_month, 4)
        self.assertTrue(
            EventParticipant.objects.filter(
                event=event,
                person=self.person,
                role=self.deceased_role,
            ).exists()
        )
        self.assertRedirects(
            response,
            reverse("people:events", args=(self.person.pk,))
            + "?sort=last_name_asc",
            fetch_redirect_response=False,
        )

        self.client.logout()
        detail = self.client.get(
            reverse("people:detail", args=(self.person.pk,))
        )
        events = self.client.get(
            reverse("people:events", args=(self.person.pk,))
        )
        self.assertNotContains(detail, "1975")
        self.assertNotContains(detail, "Zemřelá osoba")
        self.assertNotContains(events, "1975")

    def test_update_keeps_event_identity_and_every_other_participant(
        self,
    ) -> None:
        event = self.create_event(
            event_type=self.birth_type,
            role=self.born_role,
        )
        witness = EventParticipant.objects.create(
            event=event,
            person=self.witness,
            role=self.witness_role,
            note="Původní svědek",
        )
        actor = self.editor("update-editor")
        self.client.force_login(actor)

        response = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, event.pk),
            ),
            self.form_data(
                date_precision=DatePrecision.EXACT,
                start_year=1891,
                start_month=2,
                start_day=3,
                description="Opravený zápis",
            ),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        witness.refresh_from_db()
        self.assertEqual(Event.objects.filter(pk=event.pk).count(), 1)
        self.assertEqual(event.start_year, 1891)
        self.assertEqual(event.description, "Opravený zápis")
        self.assertEqual(witness.note, "Původní svědek")
        self.assertEqual(event.participants.count(), 2)
        self.assertContains(response, "3. 2. 1891")

    def test_unauthorized_posts_neither_create_nor_update(self) -> None:
        event = self.create_event(
            event_type=self.birth_type,
            role=self.born_role,
        )
        actor = self.reader()
        self.client.force_login(actor)

        create_response = self.client.post(
            reverse("people:death-create", args=(self.person.pk,)),
            self.form_data(start_year=1950),
        )
        update_response = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, event.pk),
            ),
            self.form_data(start_year=1900),
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)
        self.assertFalse(Event.objects.filter(event_type=self.death_type).exists())
        event.refresh_from_db()
        self.assertEqual(event.start_year, 1890)

    def test_anonymous_and_inactive_actor_cannot_create(self) -> None:
        url = reverse("people:birth-create", args=(self.person.pk,))

        anonymous = self.client.post(url, self.form_data())
        self.assertEqual(anonymous.status_code, 403)

        inactive = self.editor("inactive-life-event-editor")
        inactive.is_active = False
        inactive.save(update_fields=("is_active",))
        self.client.force_login(inactive)
        denied = self.client.post(url, self.form_data())

        self.assertEqual(denied.status_code, 403)
        self.assertFalse(Event.objects.exists())

    def test_hidden_other_participant_blocks_shared_event_update(self) -> None:
        event = self.create_event(
            event_type=self.birth_type,
            role=self.born_role,
        )
        self.witness.access_level = AccessLevel.RESTRICTED
        self.witness.save(update_fields=("access_level",))
        EventParticipant.objects.create(
            event=event,
            person=self.witness,
            role=self.witness_role,
            note="Skrytý svědek",
        )
        actor = self.editor("shared-event-editor")
        self.client.force_login(actor)

        response = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, event.pk),
            ),
            self.form_data(start_year=1891),
        )

        self.assertEqual(response.status_code, 404)
        event.refresh_from_db()
        self.assertEqual(event.start_year, 1890)
        self.assertNotContains(response, "Skrytý svědek", status_code=404)

    def test_invalid_duplicate_and_hidden_place_leave_no_partial_write(
        self,
    ) -> None:
        actor = self.editor("invalid-editor")
        self.client.force_login(actor)
        invalid = self.client.post(
            reverse("people:birth-create", args=(self.person.pk,)),
            self.form_data(
                date_precision=DatePrecision.EXACT,
                start_year=1890,
                start_month=2,
                start_day=31,
            ),
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(Event.objects.exists())

        hidden_place = Place.objects.create(
            name="Skryté místo",
            normalized_name="skryte misto",
            access_level=AccessLevel.RESTRICTED,
        )
        hidden_place_attempt = self.client.post(
            reverse("people:birth-create", args=(self.person.pk,)),
            self.form_data(place=hidden_place.pk),
        )
        self.assertEqual(hidden_place_attempt.status_code, 200)
        self.assertFalse(Event.objects.exists())

        self.create_event(
            event_type=self.birth_type,
            role=self.born_role,
            access_level=AccessLevel.RESTRICTED,
            year=1870,
        )
        duplicate = self.client.post(
            reverse("people:birth-create", args=(self.person.pk,)),
            self.form_data(start_year=1880),
        )
        self.assertEqual(duplicate.status_code, 403)
        self.assertNotContains(duplicate, "1870", status_code=403)
        self.assertEqual(Event.objects.count(), 1)

    def test_use_case_rechecks_proposed_access_and_place(self) -> None:
        actor = self.editor("use-case-access-editor")
        hidden_place = Place.objects.create(
            name="Nepřístupné místo",
            normalized_name="nepristupne misto",
            access_level=AccessLevel.RESTRICTED,
        )
        base_data = EventInput(
            event_type=self.birth_type,
            date_precision=DatePrecision.YEAR,
            start_year=1890,
            access_level=AccessLevel.PUBLIC,
        )

        with self.assertRaises(PermissionDenied):
            create_person_life_event(
                person=self.person,
                event_type_code="birth",
                data=replace(base_data, place=hidden_place),
                actor=actor,
            )
        with self.assertRaises(PermissionDenied):
            create_person_life_event(
                person=self.person,
                event_type_code="birth",
                data=replace(
                    base_data,
                    access_level=AccessLevel.RESTRICTED,
                ),
                actor=actor,
            )

        self.assertFalse(Event.objects.exists())

    def test_wrong_context_archived_event_and_revoked_actor_fail_closed(
        self,
    ) -> None:
        birth = self.create_event(
            event_type=self.birth_type,
            role=self.born_role,
        )
        death = self.create_event(
            event_type=self.death_type,
            role=self.deceased_role,
            year=1970,
        )
        actor = self.editor("fail-closed-editor")
        self.client.force_login(actor)

        wrong_type = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, death.pk),
            ),
            self.form_data(start_year=1900),
        )
        self.assertEqual(wrong_type.status_code, 404)

        wrong_person = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.witness.pk, birth.pk),
            ),
            self.form_data(start_year=1900),
        )
        self.assertEqual(wrong_person.status_code, 404)

        Event.objects.filter(pk=birth.pk).update(archived_at=timezone.now())
        archived = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, birth.pk),
            ),
            self.form_data(start_year=1900),
        )
        self.assertEqual(archived.status_code, 404)

        Event.objects.filter(pk=birth.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        deleted = self.client.post(
            reverse(
                "people:birth-edit",
                args=(self.person.pk, birth.pk),
            ),
            self.form_data(start_year=1900),
        )
        self.assertEqual(deleted.status_code, 404)

        hidden_place = Place.objects.create(
            name="Skryté současné místo",
            normalized_name="skryte soucasne misto",
            access_level=AccessLevel.RESTRICTED,
        )
        Event.objects.filter(pk=death.pk).update(place=hidden_place)
        hidden_current_place = self.client.post(
            reverse(
                "people:death-edit",
                args=(self.person.pk, death.pk),
            ),
            self.form_data(start_year=1971),
        )
        self.assertEqual(hidden_current_place.status_code, 404)
        Event.objects.filter(pk=death.pk).update(place=None)

        actor.groups.clear()
        add_permission = Permission.objects.get(
            content_type__app_label="events",
            codename="add_event",
        )
        self.assertFalse(actor.user_permissions.filter(pk=add_permission.pk).exists())
        revoked = self.client.post(
            reverse("people:death-create", args=(self.person.pk,)),
            self.form_data(start_year=1980),
        )
        self.assertEqual(revoked.status_code, 403)
        revoked_change = self.client.post(
            reverse(
                "people:death-edit",
                args=(self.person.pk, death.pk),
            ),
            self.form_data(start_year=1980),
        )
        self.assertEqual(revoked_change.status_code, 403)
