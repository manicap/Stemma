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
from places.models import Place, Residence, ResidenceType
from places.selectors import get_visible_person_residences

from .models import Person
from .views import person_residences


class PersonResidenceWebTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.residence_type = ResidenceType.objects.get(
            code="primary_residence"
        )

    def setUp(self) -> None:
        self.person = self.create_person("Anna", "Nováková")
        self.place = self.create_place("Praha")
        self.visible_residence = self.create_residence(
            person=self.person,
            place=self.place,
            address_text="Staré Město 12",
            note="Rodinný dům.",
            date_precision=DatePrecision.YEAR,
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=1900,
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

    def create_residence(
        self,
        *,
        person: Person | None = None,
        place: Place | None = None,
        **values: object,
    ) -> Residence:
        return Residence.objects.create(
            person=person or self.person,
            residence_type=self.residence_type,
            place=place,
            **values,
        )

    def test_visible_residence_renders_safe_presentation(self) -> None:
        response = self.client.get(
            reverse("people:residences", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Praha")
        self.assertContains(response, "Staré Město 12")
        self.assertContains(response, "Rodinný dům.")
        self.assertContains(response, self.residence_type.name)
        self.assertContains(response, "přibližně 1900")
        self.assertNotContains(response, "latitude")
        self.assertNotContains(response, "longitude")
        self.assertNotContains(response, "/mista/")

    def test_multiple_residences_and_date_shapes_render_in_order(self) -> None:
        self.create_residence(
            address_text="Brno, dlouhá historická adresa",
            date_precision=DatePrecision.RANGE,
            start_year=1910,
            end_year=1920,
        )
        self.create_residence(
            address_text="Neurčená lokalita",
            original_date_text="někdy mezi válkami",
        )

        response = self.client.get(
            reverse("people:residences", args=(self.person.pk,))
        )

        self.assertContains(response, "1910–1920")
        self.assertContains(response, "někdy mezi válkami")
        self.assertEqual(response.content.count(b'class="related-card"'), 3)

    def test_empty_and_hidden_only_residences_share_empty_state(self) -> None:
        empty_person = self.create_person("Prázdná")
        hidden_only_person = self.create_person("Bezpečně prázdná")
        secret_place = self.create_place("Utajená lokalita")
        self.create_residence(
            person=hidden_only_person,
            place=secret_place,
            access_level=AccessLevel.RESTRICTED,
        )
        empty_message = "Pro tuto osobu nejsou dostupná žádná bydliště."

        empty_response = self.client.get(
            reverse("people:residences", args=(empty_person.pk,))
        )
        hidden_response = self.client.get(
            reverse("people:residences", args=(hidden_only_person.pk,))
        )

        self.assertContains(empty_response, empty_message)
        self.assertContains(hidden_response, empty_message)
        self.assertNotContains(hidden_response, "Utajená lokalita")

    def test_full_page_htmx_and_active_tab_follow_person_shell(self) -> None:
        url = reverse("people:residences", args=(self.person.pk,))

        full_response = self.client.get(url)
        htmx_response = self.client.get(
            url,
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Seznam osob")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/person_residences.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")
        self.assertContains(
            htmx_response,
            'class="person-tab is-active"',
        )
        self.assertContains(htmx_response, 'aria-current="page"')

    def test_residence_access_levels_use_central_policy(self) -> None:
        restricted_place = self.create_place("Omezené bydliště")
        admin_place = self.create_place("Správcovské bydliště")
        self.create_residence(
            place=restricted_place,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_residence(
            place=admin_place,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:residences", args=(self.person.pk,))

        anonymous_response = self.client.get(url)
        restricted = self.user("restricted", "view_restricted_content")
        self.client.force_login(restricted)
        restricted_response = self.client.get(url)
        admin = self.user("admin", "view_admin_only_content")
        self.client.force_login(admin)
        admin_response = self.client.get(url)

        self.assertNotContains(anonymous_response, "Omezené bydliště")
        self.assertNotContains(anonymous_response, "Správcovské bydliště")
        self.assertContains(restricted_response, "Omezené bydliště")
        self.assertNotContains(restricted_response, "Správcovské bydliště")
        self.assertNotContains(admin_response, "Omezené bydliště")
        self.assertContains(admin_response, "Správcovské bydliště")

    def test_inactive_and_staff_actors_do_not_gain_content_access(self) -> None:
        restricted_place = self.create_place("Neveřejné místo")
        self.create_residence(
            place=restricted_place,
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
        url = reverse("people:residences", args=(self.person.pk,))

        for actor in actors:
            with self.subTest(username=actor.username):
                self.client.force_login(actor)
                response = self.client.get(url)
                self.assertNotContains(response, "Neveřejné místo")
                self.client.logout()

    def test_active_superuser_sees_admin_only_residence(self) -> None:
        admin_place = self.create_place("Tajné místo")
        self.create_residence(
            place=admin_place,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.client.force_login(self.user("superuser", is_superuser=True))

        response = self.client.get(
            reverse("people:residences", args=(self.person.pk,))
        )

        self.assertContains(response, "Tajné místo")

    def test_residence_and_place_lifecycle_follow_selector_contract(self) -> None:
        archived_place = self.create_place("Historické místo")
        Place.objects.filter(pk=archived_place.pk).update(
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        archived = self.create_residence(
            place=archived_place,
            address_text="Archivované bydliště",
        )
        deleted = self.create_residence(address_text="Odstraněné bydliště")
        Residence.objects.filter(pk=archived.pk).update(
            archived_at=timezone.now()
        )
        Residence.objects.filter(pk=deleted.pk).update(
            deleted_at=timezone.now()
        )

        response = self.client.get(
            reverse("people:residences", args=(self.person.pk,))
        )

        self.assertContains(response, "Historické místo")
        self.assertContains(response, "Archivované bydliště")
        self.assertNotContains(response, "Odstraněné bydliště")

    @override_settings(DEBUG=False)
    def test_hidden_and_missing_person_fail_closed_identically(self) -> None:
        hidden_person = self.create_person(
            "Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

        hidden_response = self.client.get(
            reverse("people:residences", args=(hidden_person.pk,))
        )
        missing_response = self.client.get(
            reverse("people:residences", args=(999_999,))
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
                    reverse("people:residences", args=(person.pk,))
                )
                self.assertEqual(response.status_code, 404)

    def test_view_delegates_to_actor_aware_selector_without_orm(self) -> None:
        actor = self.user("reader")
        self.client.force_login(actor)

        with patch(
            "people.views.get_visible_person_residences",
            wraps=get_visible_person_residences,
        ) as selector:
            response = self.client.get(
                reverse("people:residences", args=(self.person.pk,))
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once()
        self.assertEqual(selector.call_args.kwargs["person"], self.person)
        self.assertEqual(selector.call_args.kwargs["actor"].pk, actor.pk)
        self.assertNotIn(".objects", getsource(person_residences))

    def test_read_view_rejects_unsafe_http_methods(self) -> None:
        response = self.client.post(
            reverse("people:residences", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 405)

    def _query_count(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("people:residences", args=(self.person.pk,))
            )
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_http_query_count_does_not_grow_with_residences(self) -> None:
        baseline = self._query_count()
        for index in range(5):
            place = self.create_place(f"Další místo {index}")
            self.create_residence(
                place=place,
                address_text=f"Adresa {index}",
            )

        self.assertEqual(self._query_count(), baseline)
