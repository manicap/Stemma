from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from common.choices import AccessLevel

from .models import (
    NameType,
    Person,
    PersonName,
    Relationship,
    RelationshipType,
)
from .selectors import get_visible_people, get_visible_person


class VisiblePeopleSelectorTests(TestCase):
    def setUp(self) -> None:
        self.user_model = get_user_model()
        self.people = {
            access_level: Person.objects.create(
                first_name=access_level,
                access_level=access_level,
            )
            for access_level in AccessLevel.values
        }

    def create_user(self, username: str, **values: object):
        return self.user_model.objects.create_user(
            username=username,
            password="test-password",
            **values,
        )

    @staticmethod
    def grant(user, codename: str) -> None:
        user.user_permissions.add(Permission.objects.get(codename=codename))

    def visible_levels(self, actor) -> set[str]:
        return set(
            get_visible_people(actor=actor).values_list(
                "access_level",
                flat=True,
            )
        )

    def test_anonymous_user_sees_only_public_people(self) -> None:
        self.assertEqual(
            self.visible_levels(AnonymousUser()),
            {AccessLevel.PUBLIC},
        )

    def test_active_user_sees_public_and_authenticated_people(self) -> None:
        actor = self.create_user("reader")

        self.assertEqual(
            self.visible_levels(actor),
            {AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED},
        )

    def test_elevated_permissions_are_independent(self) -> None:
        actor = self.create_user("restricted-reader")
        self.grant(actor, "view_restricted_content")

        self.assertEqual(
            self.visible_levels(actor),
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.RESTRICTED,
            },
        )

        admin_actor = self.create_user("admin-only-reader")
        self.grant(admin_actor, "view_admin_only_content")
        self.assertEqual(
            self.visible_levels(admin_actor),
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.ADMIN_ONLY,
            },
        )

    def test_staff_flag_does_not_expand_content_access(self) -> None:
        actor = self.create_user("staff", is_staff=True)

        self.assertEqual(
            self.visible_levels(actor),
            {AccessLevel.PUBLIC, AccessLevel.AUTHENTICATED},
        )

    def test_active_superuser_sees_all_access_levels(self) -> None:
        actor = self.create_user("superuser", is_superuser=True)

        self.assertEqual(self.visible_levels(actor), set(AccessLevel.values))

    def test_inactive_privileged_user_is_treated_as_anonymous(self) -> None:
        actor = self.create_user(
            "inactive",
            is_active=False,
            is_staff=True,
            is_superuser=True,
        )

        self.assertEqual(
            self.visible_levels(actor),
            {AccessLevel.PUBLIC},
        )

    def test_default_collection_excludes_archived_and_deleted_people(
        self,
    ) -> None:
        archived = Person.objects.create(
            first_name="Archivovaná",
            archived_at="2026-08-17T12:00:00Z",
        )
        deleted = Person.objects.create(
            first_name="Odstraněná",
            deleted_at="2026-08-17T12:00:00Z",
        )
        actor = self.create_user("admin", is_superuser=True)

        visible_ids = set(
            get_visible_people(actor=actor).values_list("pk", flat=True)
        )

        self.assertNotIn(archived.pk, visible_ids)
        self.assertNotIn(deleted.pk, visible_ids)

    def test_single_person_uses_the_same_visibility_boundary(self) -> None:
        with self.assertRaises(Person.DoesNotExist):
            get_visible_person(
                person_id=self.people[AccessLevel.RESTRICTED].pk,
                actor=AnonymousUser(),
            )

    def test_actor_state_is_reloaded_from_database(self) -> None:
        actor = self.create_user("fresh-reader")
        self.grant(actor, "view_restricted_content")
        self.assertIn(
            AccessLevel.RESTRICTED,
            self.visible_levels(actor),
        )

        self.user_model.objects.filter(pk=actor.pk).update(is_active=False)

        self.assertEqual(
            self.visible_levels(actor),
            {AccessLevel.PUBLIC},
        )


class PersonWebFlowTests(TestCase):
    def setUp(self) -> None:
        self.public_person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            notes="Rodinná kronikářka.",
            access_level=AccessLevel.PUBLIC,
        )
        self.private_person = Person.objects.create(
            first_name="Skrytá",
            last_name="Osoba",
            access_level=AccessLevel.RESTRICTED,
        )

    def test_index_reads_visible_people_from_database(self) -> None:
        response = self.client.get(reverse("people:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anna")
        self.assertNotContains(response, "Skrytá")

    def test_empty_index_has_usable_message(self) -> None:
        Person.objects.all().delete()

        response = self.client.get(reverse("people:index"))

        self.assertContains(
            response,
            "Zatím zde nejsou žádné osoby, které můžete zobrazit.",
        )

    def test_visible_detail_renders_real_person_data(self) -> None:
        response = self.client.get(
            reverse("people:detail", args=(self.public_person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anna Nováková")
        self.assertContains(response, "Rodinná kronikářka.")

    def test_htmx_detail_returns_only_detail_fragment(self) -> None:
        response = self.client.get(
            reverse("people:detail", args=(self.public_person.pk,)),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "people/partials/person_detail.html")
        self.assertNotContains(response, "Seznam osob")

    @override_settings(DEBUG=False)
    def test_missing_and_invisible_detail_have_same_external_response(
        self,
    ) -> None:
        hidden_response = self.client.get(
            reverse("people:detail", args=(self.private_person.pk,))
        )
        missing_response = self.client.get(
            reverse("people:detail", args=(999_999,))
        )

        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(hidden_response.content, missing_response.content)
        self.assertContains(
            hidden_response,
            "Osoba neexistuje nebo k jejím údajům nemáte přístup.",
            status_code=404,
        )

    @override_settings(DEBUG=False)
    def test_htmx_missing_detail_has_local_usable_message(self) -> None:
        response = self.client.get(
            reverse("people:detail", args=(999_999,)),
            headers={"HX-Request": "true"},
        )

        self.assertContains(
            response,
            "Osobu se nepodařilo najít.",
            status_code=404,
        )
        self.assertNotContains(response, "<!doctype html>", status_code=404)

    def test_inactive_user_cannot_open_authenticated_detail(self) -> None:
        authenticated_person = Person.objects.create(
            first_name="Přihlášená",
            access_level=AccessLevel.AUTHENTICATED,
        )
        actor = get_user_model().objects.create_user(
            username="inactive",
            password="test-password",
            is_active=False,
        )
        self.client.force_login(actor)

        response = self.client.get(
            reverse("people:detail", args=(authenticated_person.pk,))
        )

        self.assertEqual(response.status_code, 404)

    def test_staff_without_content_permission_cannot_open_restricted_detail(
        self,
    ) -> None:
        actor = get_user_model().objects.create_user(
            username="staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(actor)

        response = self.client.get(
            reverse("people:detail", args=(self.private_person.pk,))
        )

        self.assertEqual(response.status_code, 404)

    def test_superuser_can_open_restricted_detail(self) -> None:
        actor = get_user_model().objects.create_user(
            username="superuser",
            password="test-password",
            is_superuser=True,
        )
        self.client.force_login(actor)

        response = self.client.get(
            reverse("people:detail", args=(self.private_person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Skrytá Osoba")

    def test_lifecycle_people_stay_out_of_default_list_and_detail(self) -> None:
        self.public_person.archived_at = "2026-08-17T12:00:00Z"
        self.public_person.save(update_fields=("archived_at",))
        self.private_person.deleted_at = "2026-08-17T12:00:00Z"
        self.private_person.save(update_fields=("deleted_at",))
        actor = get_user_model().objects.create_user(
            username="lifecycle-superuser",
            password="test-password",
            is_superuser=True,
        )
        self.client.force_login(actor)

        index_response = self.client.get(reverse("people:index"))
        archived_response = self.client.get(
            reverse("people:detail", args=(self.public_person.pk,))
        )
        deleted_response = self.client.get(
            reverse("people:detail", args=(self.private_person.pk,))
        )

        self.assertNotContains(index_response, "Anna Nováková")
        self.assertNotContains(index_response, "Skrytá Osoba")
        self.assertEqual(archived_response.status_code, 404)
        self.assertEqual(deleted_response.status_code, 404)

    def test_read_views_reject_unsafe_http_methods(self) -> None:
        self.assertEqual(
            self.client.post(reverse("people:index")).status_code,
            405,
        )
        self.assertEqual(
            self.client.post(
                reverse("people:detail", args=(self.public_person.pk,))
            ).status_code,
            405,
        )


class PersonAdminSecurityTests(TestCase):
    def setUp(self) -> None:
        self.public_person = Person.objects.create(first_name="Veřejná")
        self.restricted_person = Person.objects.create(
            first_name="Omezená",
            access_level=AccessLevel.RESTRICTED,
        )
        self.second_public_person = Person.objects.create(
            first_name="Druhá veřejná"
        )
        self.archived_person = Person.objects.create(
            first_name="Archivovaná tajná",
            archived_at="2026-08-17T12:00:00Z",
        )
        self.name_type = NameType.objects.create(
            code="admin-test-name",
            name="Testovací jméno",
        )
        PersonName.objects.create(
            person=self.public_person,
            name_type=self.name_type,
            value="Veřejná přezdívka",
            normalized_value="verejna prezdivka",
        )
        PersonName.objects.create(
            person=self.restricted_person,
            name_type=self.name_type,
            value="Omezená tajná přezdívka",
            normalized_value="omezena tajna prezdivka",
        )
        PersonName.objects.create(
            person=self.archived_person,
            name_type=self.name_type,
            value="Archivovaná tajná přezdívka",
            normalized_value="archivovana tajna prezdivka",
        )
        self.relationship_type = RelationshipType.objects.create(
            code="admin-test-relationship",
            name="Testovací vazba",
            forward_label_male="Známý",
            forward_label_female="Známá",
            forward_label_unknown="Známá osoba",
            reverse_label_male="Známý",
            reverse_label_female="Známá",
            reverse_label_unknown="Známá osoba",
        )
        Relationship.objects.create(
            relationship_type=self.relationship_type,
            person_a=self.public_person,
            person_b=self.second_public_person,
        )
        Relationship.objects.create(
            relationship_type=self.relationship_type,
            person_a=self.public_person,
            person_b=self.restricted_person,
        )
        self.actor = get_user_model().objects.create_user(
            username="staff-reader",
            password="test-password",
            is_staff=True,
        )
        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="view_person",
            )
        )
        self.client.force_login(self.actor)

    def test_admin_person_list_uses_central_content_visibility(self) -> None:
        response = self.client.get(reverse("admin:people_person_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veřejná")
        self.assertNotContains(response, "Omezená")

    def test_admin_person_changes_are_disabled_even_with_change_permission(
        self,
    ) -> None:
        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )

        response = self.client.post(
            reverse(
                "admin:people_person_change",
                args=(self.public_person.pk,),
            ),
            {"first_name": "Změněná"},
        )

        self.assertEqual(response.status_code, 403)
        self.public_person.refresh_from_db()
        self.assertEqual(self.public_person.first_name, "Veřejná")

    def test_related_admin_lists_cannot_reveal_hidden_people(self) -> None:
        self.actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="view_personname",
            ),
            Permission.objects.get(
                content_type__app_label="people",
                codename="view_relationship",
            ),
        )

        names_response = self.client.get(
            reverse("admin:people_personname_changelist")
        )
        relationships_response = self.client.get(
            reverse("admin:people_relationship_changelist")
        )

        self.assertContains(names_response, "Veřejná přezdívka")
        self.assertNotContains(names_response, "Omezená tajná přezdívka")
        self.assertNotContains(names_response, "Archivovaná tajná přezdívka")
        self.assertContains(relationships_response, "Druhá veřejná")
        self.assertNotContains(relationships_response, "Omezená")
