from decimal import Decimal
from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel
from places.choices import GraveSiteStatus
from places.models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
    Place,
)
from places.selectors import get_visible_person_grave_site_links

from .models import Person
from .views import person_grave_sites


class PersonGraveSiteWebTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.grave_site_type = GraveSiteType.objects.get(code="grave")
        cls.role = PersonGraveSiteRole.objects.get(code="buried")

    def setUp(self) -> None:
        self.person = self.create_person("Anna", "Nováková")
        self.place = self.create_place("Praha")
        self.grave_site = self.create_grave_site(
            place=self.place,
            cemetery_name="Olšanské hřbitovy",
            location_text="Historická část hřbitova",
            section="12",
            row="4",
            grave_number="27",
            status=GraveSiteStatus.EXISTING,
            latitude=Decimal("50.081000"),
            longitude=Decimal("14.469000"),
            inscription="Nezobrazovaný přepis nápisu",
        )
        self.visible_link = self.create_link(
            grave_site=self.grave_site,
            note="Rodinné hrobové místo.",
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

    def create_grave_site(self, **values: object) -> GraveSite:
        values.setdefault("location_text", "U hlavní cesty")
        return GraveSite.objects.create(
            grave_site_type=self.grave_site_type,
            **values,
        )

    def create_link(
        self,
        *,
        person: Person | None = None,
        grave_site: GraveSite | None = None,
        **values: object,
    ) -> PersonGraveSite:
        return PersonGraveSite.objects.create(
            person=person or self.person,
            grave_site=grave_site or self.grave_site,
            role=self.role,
            **values,
        )

    def test_visible_grave_site_renders_safe_presentation(self) -> None:
        response = self.client.get(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Olšanské hřbitovy")
        self.assertContains(response, "Historická část hřbitova")
        self.assertContains(response, "Praha")
        self.assertContains(response, "Oddíl 12 · Řada 4 · Hrob 27")
        self.assertContains(response, self.grave_site_type.name)
        self.assertContains(response, self.role.name)
        self.assertContains(response, "Existující")
        self.assertContains(response, "Rodinné hrobové místo.")
        self.assertNotContains(response, "50.081000")
        self.assertNotContains(response, "14.469000")
        self.assertNotContains(response, "Nezobrazovaný přepis nápisu")
        self.assertNotContains(response, "/mista/")

    def test_multiple_grave_sites_render_in_selector_order(self) -> None:
        first_site = self.create_grave_site(
            cemetery_name="A – dlouhý název hřbitova a pamětního místa",
            section="A",
            row="1",
            grave_number="2",
            status=GraveSiteStatus.DESTROYED,
        )
        self.create_link(grave_site=first_site)

        response = self.client.get(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertContains(response, "A – dlouhý název")
        self.assertContains(response, "Zaniklé")
        self.assertEqual(response.content.count(b'class="related-card"'), 2)
        content = response.content.decode()
        self.assertLess(
            content.index("A – dlouhý název"),
            content.index("Olšanské hřbitovy"),
        )

    def test_empty_and_hidden_only_sites_share_empty_state(self) -> None:
        empty_person = self.create_person("Prázdná")
        hidden_person = self.create_person("Bezpečně prázdná")
        secret_place = self.create_place("Utajené místo")
        secret_site = self.create_grave_site(
            place=secret_place,
            location_text="Skrytá lokalita",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(person=hidden_person, grave_site=secret_site)
        empty_message = (
            "Pro tuto osobu nejsou dostupná žádná hrobová místa."
        )

        empty_response = self.client.get(
            reverse("people:grave-sites", args=(empty_person.pk,))
        )
        hidden_response = self.client.get(
            reverse("people:grave-sites", args=(hidden_person.pk,))
        )

        self.assertContains(empty_response, empty_message)
        self.assertContains(hidden_response, empty_message)
        self.assertNotContains(hidden_response, "Utajené místo")
        self.assertNotContains(hidden_response, "Skrytá lokalita")

    def test_full_page_htmx_and_active_tab_follow_person_shell(self) -> None:
        url = reverse("people:grave-sites", args=(self.person.pk,))

        full_response = self.client.get(url)
        htmx_response = self.client.get(
            url,
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Seznam osob")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/person_grave_sites.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")
        self.assertContains(
            htmx_response,
            'class="person-tab is-active"',
        )
        self.assertContains(htmx_response, 'aria-current="page"')

    def test_access_levels_use_central_policy(self) -> None:
        restricted_site = self.create_grave_site(
            location_text="Omezené hrobové místo",
        )
        admin_site = self.create_grave_site(
            location_text="Správcovské hrobové místo",
        )
        self.create_link(
            grave_site=restricted_site,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(
            grave_site=admin_site,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:grave-sites", args=(self.person.pk,))

        anonymous_response = self.client.get(url)
        restricted = self.user("restricted", "view_restricted_content")
        self.client.force_login(restricted)
        restricted_response = self.client.get(url)
        admin = self.user("admin", "view_admin_only_content")
        self.client.force_login(admin)
        admin_response = self.client.get(url)

        self.assertNotContains(anonymous_response, "Omezené hrobové místo")
        self.assertNotContains(anonymous_response, "Správcovské hrobové místo")
        self.assertContains(restricted_response, "Omezené hrobové místo")
        self.assertNotContains(restricted_response, "Správcovské hrobové místo")
        self.assertNotContains(admin_response, "Omezené hrobové místo")
        self.assertContains(admin_response, "Správcovské hrobové místo")

    def test_inactive_and_staff_actors_do_not_gain_content_access(self) -> None:
        private_site = self.create_grave_site(
            location_text="Neveřejné hrobové místo",
        )
        self.create_link(
            grave_site=private_site,
            access_level=AccessLevel.RESTRICTED,
        )
        actors = (
            self.user(
                "inactive",
                "view_restricted_content",
                is_active=False,
            ),
            self.user("staff", is_staff=True),
        )
        url = reverse("people:grave-sites", args=(self.person.pk,))

        for actor in actors:
            with self.subTest(username=actor.username):
                self.client.force_login(actor)
                response = self.client.get(url)
                self.assertNotContains(response, "Neveřejné hrobové místo")
                self.client.logout()

    def test_active_superuser_sees_admin_only_grave_site(self) -> None:
        private_site = self.create_grave_site(
            location_text="Tajné hrobové místo",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.create_link(
            grave_site=private_site,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.client.force_login(self.user("superuser", is_superuser=True))

        response = self.client.get(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertContains(response, "Tajné hrobové místo")

    def test_lifecycle_follows_selector_contract(self) -> None:
        archived_site = self.create_grave_site(
            location_text="Archivované hrobové místo",
            archived_at=timezone.now(),
        )
        destroyed_site = self.create_grave_site(
            location_text="Zaniklé hrobové místo",
            status=GraveSiteStatus.DESTROYED,
        )
        deleted_site = self.create_grave_site(
            location_text="Odstraněné hrobové místo",
            deleted_at=timezone.now(),
        )
        archived_link = self.create_link(grave_site=archived_site)
        self.create_link(grave_site=destroyed_site)
        self.create_link(grave_site=deleted_site)
        deleted_link_site = self.create_grave_site(
            location_text="Místo odstraněné vazby"
        )
        deleted_link = self.create_link(grave_site=deleted_link_site)
        PersonGraveSite.objects.filter(pk=archived_link.pk).update(
            archived_at=timezone.now()
        )
        PersonGraveSite.objects.filter(pk=deleted_link.pk).update(
            deleted_at=timezone.now()
        )

        response = self.client.get(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertContains(response, "Archivované hrobové místo")
        self.assertContains(response, "Zaniklé hrobové místo")
        self.assertNotContains(response, "Odstraněné hrobové místo")
        self.assertNotContains(response, "Místo odstraněné vazby")

    def test_place_is_text_context_without_separate_link(self) -> None:
        historical_place = self.create_place(
            "Soukromé historické místo",
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        grave_site = self.create_grave_site(
            place=historical_place,
            location_text="Veřejné pamětní místo",
        )
        self.create_link(grave_site=grave_site)

        response = self.client.get(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertContains(response, "Soukromé historické místo")
        self.assertNotContains(response, "/mista/")

    @override_settings(DEBUG=False)
    def test_hidden_and_missing_person_fail_closed_identically(self) -> None:
        hidden_person = self.create_person(
            "Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

        hidden_response = self.client.get(
            reverse("people:grave-sites", args=(hidden_person.pk,))
        )
        missing_response = self.client.get(
            reverse("people:grave-sites", args=(999_999,))
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(hidden_response.content, missing_response.content)

    def test_archived_and_deleted_parent_stay_out_of_person_ui(self) -> None:
        archived = self.create_person("Archivovaná", archived=True)
        deleted = self.create_person("Odstraněná", deleted=True)
        self.client.force_login(
            self.user("lifecycle-superuser", is_superuser=True)
        )

        for person in (archived, deleted):
            with self.subTest(person=person.pk):
                response = self.client.get(
                    reverse("people:grave-sites", args=(person.pk,))
                )
                self.assertEqual(response.status_code, 404)

    def test_view_delegates_to_actor_aware_selector_without_orm(self) -> None:
        actor = self.user("reader")
        self.client.force_login(actor)

        with patch(
            "people.views.get_visible_person_grave_site_links",
            wraps=get_visible_person_grave_site_links,
        ) as selector:
            response = self.client.get(
                reverse("people:grave-sites", args=(self.person.pk,))
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once()
        self.assertEqual(selector.call_args.kwargs["person"], self.person)
        self.assertEqual(selector.call_args.kwargs["actor"].pk, actor.pk)
        self.assertNotIn(".objects", getsource(person_grave_sites))

    def test_read_view_rejects_unsafe_http_methods(self) -> None:
        response = self.client.post(
            reverse("people:grave-sites", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 405)

    def _query_count(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("people:grave-sites", args=(self.person.pk,))
            )
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_http_query_count_does_not_grow_with_grave_sites(self) -> None:
        baseline = self._query_count()
        for index in range(5):
            place = self.create_place(f"Další místo {index}")
            grave_site = self.create_grave_site(
                place=place,
                cemetery_name=f"Další hřbitov {index}",
            )
            self.create_link(grave_site=grave_site)

        self.assertEqual(self._query_count(), baseline)
