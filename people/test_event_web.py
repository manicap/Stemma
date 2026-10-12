from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision, DateQualifier
from events.models import Event, EventParticipant, EventType, ParticipantRole
from events.selectors import get_visible_person_events
from places.models import Place

from .models import Person
from .views import person_events


class PersonEventWebTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.event_type = EventType.objects.get(code="other")
        cls.role = ParticipantRole.objects.get(code="other")

    def setUp(self) -> None:
        self.person = self.create_person("Anna", "Nováková")
        self.place = self.create_place("Praha")
        self.visible_event = self.create_event(
            title="Rodinné setkání",
            description="Dlouhý, ale bezpečný popis rodinné události.",
            place=self.place,
            location_detail="Staré Město",
            date_precision=DatePrecision.YEAR,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1920,
        )

    @staticmethod
    def grant(actor, codename: str) -> None:
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                content_type__model="user",
                codename=codename,
            )
        )

    def user(self, username: str, *permissions: str, **values: object):
        actor = get_user_model().objects.create_user(
            username=username,
            password="test-password",
            **values,
        )
        for codename in permissions:
            self.grant(actor, codename)
        return actor

    @staticmethod
    def create_person(
        first_name: str,
        last_name: str = "Testovací",
        *,
        access_level: str = AccessLevel.PUBLIC,
        archived: bool = False,
        deleted: bool = False,
    ) -> Person:
        now = timezone.now()
        return Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            access_level=access_level,
            archived_at=now if archived else None,
            deleted_at=now if deleted else None,
        )

    @staticmethod
    def create_place(name: str, **values: object) -> Place:
        return Place.objects.create(
            name=name,
            normalized_name=name.casefold(),
            **values,
        )

    def create_event(
        self,
        *,
        person: Person | None = None,
        **values: object,
    ) -> Event:
        event = Event.objects.create(event_type=self.event_type, **values)
        EventParticipant.objects.create(
            event=event,
            person=person or self.person,
            role=self.role,
        )
        return event

    def test_event_renders_safe_overview_and_incomplete_date(self) -> None:
        response = self.client.get(
            reverse("people:events", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rodinné setkání")
        self.assertContains(response, self.event_type.name)
        self.assertContains(response, "přibližně 1920")
        self.assertContains(response, "Praha")
        self.assertContains(response, "Staré Město")
        self.assertContains(response, "Dlouhý, ale bezpečný popis")
        self.assertNotContains(response, "/mista/")
        self.assertNotContains(response, "Přílohy")
        self.assertNotContains(response, "Zdroje")

    def test_multiple_events_render_in_selector_order(self) -> None:
        self.create_event(title="Dřívější", start_year=1900)

        response = self.client.get(
            reverse("people:events", args=(self.person.pk,))
        )

        content = response.content.decode()
        self.assertEqual(response.content.count(b'class="related-card"'), 2)
        self.assertLess(content.index("Dřívější"), content.index("Rodinné"))

    def test_empty_and_hidden_only_events_share_empty_state(self) -> None:
        empty_person = self.create_person("Prázdná")
        hidden_person = self.create_person("Bezpečně prázdná")
        self.create_event(
            person=hidden_person,
            title="Utajená událost",
            access_level=AccessLevel.RESTRICTED,
        )
        message = "Pro tuto osobu nejsou dostupné žádné události."

        empty_response = self.client.get(
            reverse("people:events", args=(empty_person.pk,))
        )
        hidden_response = self.client.get(
            reverse("people:events", args=(hidden_person.pk,))
        )

        self.assertContains(empty_response, message)
        self.assertContains(hidden_response, message)
        self.assertNotContains(hidden_response, "Utajená událost")

    def test_full_page_htmx_and_active_tab_follow_person_shell(self) -> None:
        url = reverse("people:events", args=(self.person.pk,))

        full_response = self.client.get(url)
        htmx_response = self.client.get(url, headers={"HX-Request": "true"})

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Seznam osob")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/person_events.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")
        self.assertContains(htmx_response, 'class="person-tab is-active"')
        self.assertContains(htmx_response, 'aria-current="page"')

    def test_access_levels_use_central_policy(self) -> None:
        self.create_event(
            title="Omezená událost",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_event(
            title="Správcovská událost",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:events", args=(self.person.pk,))

        anonymous = self.client.get(url)
        restricted = self.user("restricted-web", "view_restricted_content")
        self.client.force_login(restricted)
        restricted_response = self.client.get(url)
        admin = self.user("admin-web", "view_admin_only_content")
        self.client.force_login(admin)
        admin_response = self.client.get(url)

        self.assertNotContains(anonymous, "Omezená událost")
        self.assertNotContains(anonymous, "Správcovská událost")
        self.assertContains(restricted_response, "Omezená událost")
        self.assertNotContains(restricted_response, "Správcovská událost")
        self.assertNotContains(admin_response, "Omezená událost")
        self.assertContains(admin_response, "Správcovská událost")

    def test_inactive_staff_and_superuser_follow_central_policy(self) -> None:
        self.create_event(
            title="Neveřejná událost",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:events", args=(self.person.pk,))
        inactive = self.user(
            "inactive-web",
            "view_admin_only_content",
            is_active=False,
        )
        staff = self.user("staff-web", is_staff=True)
        superuser = self.user("super-web", is_superuser=True)

        for actor in (inactive, staff):
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertNotContains(
                    self.client.get(url),
                    "Neveřejná událost",
                )
                self.client.logout()
        self.client.force_login(superuser)
        self.assertContains(self.client.get(url), "Neveřejná událost")

    def test_lifecycle_excludes_archived_and_deleted_events(self) -> None:
        archived = self.create_event(title="Archivovaná událost")
        deleted = self.create_event(title="Odstraněná událost")
        Event.objects.filter(pk=archived.pk).update(
            archived_at=timezone.now()
        )
        Event.objects.filter(pk=deleted.pk).update(deleted_at=timezone.now())

        response = self.client.get(
            reverse("people:events", args=(self.person.pk,))
        )

        self.assertNotContains(response, "Archivovaná událost")
        self.assertNotContains(response, "Odstraněná událost")

    def test_hidden_participant_and_place_do_not_leak(self) -> None:
        hidden = self.create_person(
            "Přísně utajená",
            "Účastnice",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        EventParticipant.objects.create(
            event=self.visible_event,
            person=hidden,
            role=self.role,
        )
        hidden_place = self.create_place(
            "Přísně utajené místo",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        archived_place = self.create_place(
            "Archivovaný Place kontext",
            archived_at=timezone.now(),
        )
        deleted_place = self.create_place(
            "Odstraněný Place kontext",
            deleted_at=timezone.now(),
        )
        self.create_event(title="Veřejný kontext", place=hidden_place)
        self.create_event(title="Veřejná archivovaná vazba", place=archived_place)
        self.create_event(title="Veřejná odstraněná vazba", place=deleted_place)

        response = self.client.get(
            reverse("people:events", args=(self.person.pk,))
        )

        self.assertContains(response, "Veřejný kontext")
        self.assertNotContains(response, "Přísně utajená")
        self.assertNotContains(response, "Účastnice")
        self.assertNotContains(response, "Přísně utajené místo")
        self.assertNotContains(response, "Archivovaný Place kontext")
        self.assertNotContains(response, "Odstraněný Place kontext")
        self.assertNotContains(response, f"/osoby/{hidden.pk}/")

    @override_settings(DEBUG=False)
    def test_hidden_and_missing_person_fail_closed_identically(self) -> None:
        hidden = self.create_person(
            "Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

        hidden_response = self.client.get(
            reverse("people:events", args=(hidden.pk,))
        )
        missing_response = self.client.get(
            reverse("people:events", args=(999_999,))
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(hidden_response.content, missing_response.content)

    def test_archived_and_deleted_parent_stay_out_of_person_ui(self) -> None:
        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        self.client.force_login(self.user("lifecycle-super", is_superuser=True))

        for person in (archived, deleted):
            with self.subTest(person=person.pk):
                response = self.client.get(
                    reverse("people:events", args=(person.pk,))
                )
                self.assertEqual(response.status_code, 404)

    def test_view_delegates_to_actor_aware_selector_without_orm(self) -> None:
        actor = self.user("reader-web")
        self.client.force_login(actor)

        with patch(
            "people.views.get_visible_person_events",
            wraps=get_visible_person_events,
        ) as selector:
            response = self.client.get(
                reverse("people:events", args=(self.person.pk,))
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once()
        self.assertEqual(selector.call_args.kwargs["person"], self.person)
        self.assertEqual(selector.call_args.kwargs["actor"].pk, actor.pk)
        self.assertNotIn(".objects", getsource(person_events))

    def test_read_view_rejects_unsafe_http_methods(self) -> None:
        response = self.client.post(
            reverse("people:events", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 405)

    def _query_count(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("people:events", args=(self.person.pk,))
            )
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_http_query_count_does_not_grow_with_events(self) -> None:
        baseline = self._query_count()
        for index in range(5):
            self.create_event(title=f"Další událost {index}")

        self.assertEqual(self._query_count(), baseline)
