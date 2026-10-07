from inspect import getsource
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision

from .models import Person, Relationship, RelationshipType
from .selectors import get_visible_relationship_overview
from .views import person_relationships


class PersonRelationshipWebTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.relationship_types = {
            relationship_type.code: relationship_type
            for relationship_type in RelationshipType.objects.all()
        }

    def setUp(self) -> None:
        self.person = self.create_person("Anna", "Nováková")
        self.public_partner = self.create_person("Bohdan", "Novák")
        self.create_relationship(
            "partner",
            self.person,
            self.public_partner,
        )
        self.relationship_year = 1900

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

    def create_relationship(
        self,
        code: str,
        person_a: Person,
        person_b: Person,
        *,
        access_level: str = AccessLevel.PUBLIC,
    ) -> Relationship:
        self.relationship_year = getattr(self, "relationship_year", 1900) + 1
        return Relationship.objects.create(
            relationship_type=self.relationship_types[code],
            person_a=person_a,
            person_b=person_b,
            access_level=access_level,
            date_precision=DatePrecision.YEAR,
            start_year=self.relationship_year,
        )

    def test_visible_relationships_render_safe_labels_and_links(self) -> None:
        response = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bohdan Novák")
        self.assertContains(response, "partner")
        self.assertContains(
            response,
            reverse("people:detail", args=(self.public_partner.pk,)),
        )
        self.assertNotContains(response, "relationship_ids")

    def test_empty_and_hidden_only_relationships_share_empty_state(self) -> None:
        empty_person = self.create_person("Prázdná")
        hidden_only_person = self.create_person("Bezpečně prázdná")
        hidden_partner = self.create_person(
            "Utajená",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.create_relationship(
            "family_friend",
            hidden_only_person,
            hidden_partner,
        )
        empty_message = "Pro tuto osobu nejsou dostupné žádné vztahy."

        empty_response = self.client.get(
            reverse("people:relationships", args=(empty_person.pk,))
        )
        hidden_response = self.client.get(
            reverse("people:relationships", args=(hidden_only_person.pk,))
        )

        self.assertContains(empty_response, empty_message)
        self.assertContains(hidden_response, empty_message)
        self.assertNotContains(hidden_response, "Utajená")
        self.assertNotContains(
            hidden_response,
            reverse("people:detail", args=(hidden_partner.pk,)),
        )

    def test_full_page_htmx_and_active_tab_follow_person_shell(self) -> None:
        url = reverse("people:relationships", args=(self.person.pk,))

        full_response = self.client.get(url)
        htmx_response = self.client.get(
            url,
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(full_response, "people/person_shell.html")
        self.assertContains(full_response, "Seznam osob")
        self.assertTemplateUsed(
            htmx_response,
            "people/partials/person_relationships.html",
        )
        self.assertNotContains(htmx_response, "Seznam osob")
        self.assertContains(
            htmx_response,
            'class="person-tab is-active"',
        )
        self.assertContains(htmx_response, 'aria-current="page"')

    def test_relationship_access_levels_use_central_policy(self) -> None:
        restricted_partner = self.create_person(
            "Omezený",
            access_level=AccessLevel.RESTRICTED,
        )
        admin_partner = self.create_person(
            "Správcovský",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.create_relationship(
            "spouse",
            self.person,
            restricted_partner,
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "family_friend",
            self.person,
            admin_partner,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        url = reverse("people:relationships", args=(self.person.pk,))

        anonymous_response = self.client.get(url)
        restricted_actor = self.user("restricted", "view_restricted_content")
        self.client.force_login(restricted_actor)
        restricted_response = self.client.get(url)
        admin_actor = self.user("admin", "view_admin_only_content")
        self.client.force_login(admin_actor)
        admin_response = self.client.get(url)

        self.assertNotContains(anonymous_response, "Omezený")
        self.assertNotContains(anonymous_response, "Správcovský")
        self.assertContains(restricted_response, "Omezený")
        self.assertNotContains(restricted_response, "Správcovský")
        self.assertNotContains(admin_response, "Omezený")
        self.assertContains(admin_response, "Správcovský")

    def test_inactive_and_staff_actors_do_not_gain_content_access(self) -> None:
        restricted_partner = self.create_person(
            "Neveřejný",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "spouse",
            self.person,
            restricted_partner,
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
        url = reverse("people:relationships", args=(self.person.pk,))

        for actor in actors:
            with self.subTest(username=actor.username):
                self.client.force_login(actor)
                response = self.client.get(url)
                self.assertNotContains(response, "Neveřejný")
                self.client.logout()

    def test_active_superuser_sees_admin_only_relationship(self) -> None:
        admin_partner = self.create_person(
            "Tajná",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.create_relationship(
            "family_friend",
            self.person,
            admin_partner,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.client.force_login(self.user("superuser", is_superuser=True))

        response = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )

        self.assertContains(response, "Tajná")
        self.assertContains(
            response,
            reverse("people:detail", args=(admin_partner.pk,)),
        )

    def test_archived_visible_counterpart_has_no_unusable_link(self) -> None:
        archived_partner = self.create_person("Historická", archived=True)
        self.create_relationship(
            "family_friend",
            self.person,
            archived_partner,
        )
        self.client.force_login(
            self.user("archived-reader", is_superuser=True)
        )

        response = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )

        self.assertContains(response, "Historická")
        self.assertNotContains(
            response,
            reverse("people:detail", args=(archived_partner.pk,)),
        )

    @override_settings(DEBUG=False)
    def test_hidden_and_missing_person_fail_closed_identically(self) -> None:
        hidden_person = self.create_person(
            "Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

        hidden_response = self.client.get(
            reverse("people:relationships", args=(hidden_person.pk,))
        )
        missing_response = self.client.get(
            reverse("people:relationships", args=(999_999,))
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
                    reverse("people:relationships", args=(person.pk,))
                )
                self.assertEqual(response.status_code, 404)

    def test_view_delegates_to_actor_aware_selector_without_orm(self) -> None:
        actor = self.user("reader")
        self.client.force_login(actor)

        with patch(
            "people.views.get_visible_relationship_overview",
            wraps=get_visible_relationship_overview,
        ) as selector:
            response = self.client.get(
                reverse("people:relationships", args=(self.person.pk,))
            )

        self.assertEqual(response.status_code, 200)
        selector.assert_called_once()
        self.assertEqual(selector.call_args.kwargs["person"], self.person)
        self.assertEqual(selector.call_args.kwargs["actor"].pk, actor.pk)
        self.assertNotIn(".objects", getsource(person_relationships))

    def test_read_view_rejects_unsafe_http_methods(self) -> None:
        response = self.client.post(
            reverse("people:relationships", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 405)

    def _query_count(self) -> int:
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(
                reverse("people:relationships", args=(self.person.pk,))
            )
        self.assertEqual(response.status_code, 200)
        return len(captured)

    def test_http_query_count_does_not_grow_with_relationships(self) -> None:
        baseline = self._query_count()
        for index in range(5):
            partner = self.create_person(f"Partner {index}")
            self.create_relationship("family_friend", self.person, partner)

        self.assertEqual(self._query_count(), baseline)
