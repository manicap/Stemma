from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)

from .models import Person, Relationship, RelationshipType
from .use_cases import (
    PersonRelationshipInput,
    create_person_relationship,
    update_person_relationship,
)


class PersonRelationshipWriteWebTests(TestCase):
    """HTTP and security boundaries of the person-centric relationship UI."""

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            access_level=AccessLevel.PUBLIC,
        )
        self.other = Person.objects.create(
            first_name="Bohdan",
            last_name="Novák",
            access_level=AccessLevel.PUBLIC,
        )

    def editor(self, username: str = "relationship-editor"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Editor"))
        return actor

    def reader(self, username: str = "relationship-reader"):
        actor = get_user_model().objects.create_user(username=username)
        actor.groups.add(Group.objects.get(name="Čtenář"))
        return actor

    def form_data(self, **overrides: object) -> dict[str, object]:
        values: dict[str, object] = {
            "other_person": self.other.pk,
            "date_precision": DatePrecision.UNKNOWN,
            "date_qualifier": DateQualifier.NONE,
            "start_year": "",
            "start_month": "",
            "start_day": "",
            "end_year": "",
            "end_month": "",
            "end_day": "",
            "original_date_text": "",
            "date_note": "",
            "note": "Rodinný zápis",
            "access_level": AccessLevel.PUBLIC,
            "verification_status": VerificationStatus.UNCONFIRMED,
        }
        values.update(overrides)
        return values

    def test_editor_creates_parent_with_htmx_context_and_both_sides_render(
        self,
    ) -> None:
        actor = self.editor()
        self.assertTrue(actor.has_perm("people.add_relationship"))
        self.assertTrue(actor.has_perm("people.change_relationship"))
        self.client.force_login(actor)

        response = self.client.post(
            reverse(
                "people:relationship-create",
                args=(self.person.pk, "parent"),
            )
            + "?q=anna&sort=oldest",
            self.form_data(),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        relationship = Relationship.objects.get()
        self.assertEqual(relationship.relationship_type.code, "biological_parent")
        self.assertEqual(relationship.person_a, self.other)
        self.assertEqual(relationship.person_b, self.person)
        self.assertEqual(relationship.created_by, actor)
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:relationships", args=(self.person.pk,))
            + "?q=anna&sort=oldest",
        )
        self.assertContains(response, "Vazba byla uložena.")
        self.assertContains(response, "Bohdan Novák")
        self.assertContains(
            response,
            reverse(
                "people:relationship-edit",
                args=(self.person.pk, relationship.pk),
            ),
        )

        other_side = self.client.get(
            reverse("people:relationships", args=(self.other.pk,))
        )
        self.assertContains(other_side, "Anna Nováková")
        self.assertContains(other_side, "dítě")

    def test_partner_is_stored_once_and_visible_from_both_people(self) -> None:
        self.client.force_login(self.editor("partner-editor"))

        response = self.client.post(
            reverse(
                "people:relationship-create",
                args=(self.person.pk, "partner"),
            ),
            self.form_data(),
        )

        self.assertRedirects(
            response,
            reverse("people:relationships", args=(self.person.pk,)),
        )
        relationship = Relationship.objects.get()
        self.assertEqual(relationship.relationship_type.code, "partner")
        self.assertEqual(
            (relationship.person_a_id, relationship.person_b_id),
            tuple(sorted((self.person.pk, self.other.pk))),
        )
        for person, expected_name in (
            (self.person, "Bohdan Novák"),
            (self.other, "Anna Nováková"),
        ):
            with self.subTest(person=person.pk):
                detail = self.client.get(
                    reverse("people:relationships", args=(person.pk,))
                )
                self.assertContains(detail, expected_name)
                self.assertContains(detail, "partner")
        self.assertEqual(Relationship.objects.count(), 1)

    def test_direct_post_requires_current_active_permission(self) -> None:
        url = reverse(
            "people:relationship-create",
            args=(self.person.pk, "child"),
        )
        anonymous = self.client.post(url, self.form_data())
        self.assertEqual(anonymous.status_code, 403)

        self.client.force_login(self.reader())
        reader = self.client.post(url, self.form_data())
        self.assertEqual(reader.status_code, 403)

        inactive = self.editor("inactive-relationship-editor")
        inactive.is_active = False
        inactive.save(update_fields=("is_active",))
        self.client.force_login(inactive)
        denied = self.client.post(url, self.form_data())
        self.assertEqual(denied.status_code, 403)
        self.assertFalse(Relationship.objects.exists())

    def test_picker_and_tampered_post_do_not_expose_hidden_person(self) -> None:
        hidden = Person.objects.create(
            first_name="Skrytá",
            last_name="Osoba",
            access_level=AccessLevel.RESTRICTED,
        )
        self.client.force_login(self.editor("picker-editor"))
        url = reverse(
            "people:relationship-create",
            args=(self.person.pk, "child"),
        )

        form_response = self.client.get(url)
        self.assertContains(form_response, "Vyhledat existující osobu")
        self.assertContains(form_response, "Bohdan Novák")
        self.assertNotContains(form_response, "Skrytá Osoba")

        tampered = self.client.post(
            url,
            self.form_data(other_person=hidden.pk),
        )
        self.assertEqual(tampered.status_code, 200)
        self.assertContains(tampered, "Vyberte platnou možnost")
        self.assertNotContains(tampered, "Skrytá Osoba")
        self.assertFalse(Relationship.objects.exists())

    def test_duplicate_is_atomic_and_edit_preserves_type_and_people(self) -> None:
        actor = self.editor("edit-relationship-editor")
        self.client.force_login(actor)
        create_url = reverse(
            "people:relationship-create",
            args=(self.person.pk, "child"),
        )
        first = self.client.post(create_url, self.form_data())
        self.assertEqual(first.status_code, 302)
        relationship = Relationship.objects.get()

        duplicate = self.client.post(create_url, self.form_data())
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "Stejná vazba")
        self.assertEqual(Relationship.objects.count(), 1)

        third = Person.objects.create(
            first_name="Cyril",
            last_name="Jiný",
            access_level=AccessLevel.PUBLIC,
        )
        original_context = (
            relationship.pk,
            relationship.relationship_type_id,
            relationship.person_a_id,
            relationship.person_b_id,
        )
        edited = self.client.post(
            reverse(
                "people:relationship-edit",
                args=(self.person.pk, relationship.pk),
            ),
            self.form_data(
                other_person=third.pk,
                note="Opravená poznámka",
                access_level=AccessLevel.AUTHENTICATED,
                relationship_type=RelationshipType.objects.get(
                    code="guardian"
                ).pk,
                person_a=third.pk,
                person_b=third.pk,
                created_by=third.pk,
                archived_at=timezone.now().isoformat(),
            ),
        )
        self.assertEqual(edited.status_code, 302)
        relationship.refresh_from_db()
        self.assertEqual(
            (
                relationship.pk,
                relationship.relationship_type_id,
                relationship.person_a_id,
                relationship.person_b_id,
            ),
            original_context,
        )
        self.assertEqual(relationship.note, "Opravená poznámka")
        self.assertEqual(
            relationship.access_level,
            AccessLevel.AUTHENTICATED,
        )

    def test_edit_fails_closed_when_other_person_becomes_hidden(self) -> None:
        self.client.force_login(self.editor("hidden-context-editor"))
        self.client.post(
            reverse(
                "people:relationship-create",
                args=(self.person.pk, "partner"),
            ),
            self.form_data(),
        )
        relationship = Relationship.objects.get()
        self.other.access_level = AccessLevel.RESTRICTED
        self.other.save(update_fields=("access_level",))

        response = self.client.post(
            reverse(
                "people:relationship-edit",
                args=(self.person.pk, relationship.pk),
            ),
            self.form_data(note="Nesmí se uložit"),
        )

        self.assertEqual(response.status_code, 404)
        relationship.refresh_from_db()
        self.assertEqual(relationship.note, "Rodinný zápis")
        self.assertNotContains(response, "Skrytá", status_code=404)

    def test_add_and_change_permissions_are_independent(self) -> None:
        add_actor = get_user_model().objects.create_user(
            username="relationship-add-only"
        )
        add_actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="add_relationship",
            )
        )
        self.client.force_login(add_actor)
        created = self.client.post(
            reverse(
                "people:relationship-create",
                args=(self.person.pk, "partner"),
            ),
            self.form_data(),
        )
        self.assertEqual(created.status_code, 302)
        relationship = Relationship.objects.get()
        denied_edit = self.client.get(
            reverse(
                "people:relationship-edit",
                args=(self.person.pk, relationship.pk),
            )
        )
        self.assertEqual(denied_edit.status_code, 403)

        change_actor = get_user_model().objects.create_user(
            username="relationship-change-only"
        )
        change_actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_relationship",
            )
        )
        self.client.force_login(change_actor)
        get_lock_models: list[str] = []
        original_select_for_update = QuerySet.select_for_update

        def record_get_lock(queryset, *args, **kwargs):
            get_lock_models.append(queryset.model._meta.label)
            return original_select_for_update(queryset, *args, **kwargs)

        with patch.object(QuerySet, "select_for_update", record_get_lock):
            allowed_edit = self.client.get(
                reverse(
                    "people:relationship-edit",
                    args=(self.person.pk, relationship.pk),
                )
            )
        denied_create = self.client.get(
            reverse(
                "people:relationship-create",
                args=(self.person.pk, "child"),
            )
        )
        self.assertEqual(allowed_edit.status_code, 200)
        self.assertEqual(get_lock_models, [])
        self.assertEqual(denied_create.status_code, 403)

    def test_historical_contexts_render_without_edit_actions(self) -> None:
        archived_relationship = Relationship.objects.create(
            relationship_type=RelationshipType.objects.get(code="partner"),
            person_a=self.person,
            person_b=self.other,
            archived_at=timezone.now(),
        )
        archived_other = Person.objects.create(
            first_name="Historická",
            last_name="Osoba",
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        active_with_archived_person = Relationship.objects.create(
            relationship_type=RelationshipType.objects.get(
                code="family_friend"
            ),
            person_a=self.person,
            person_b=archived_other,
        )
        actor = get_user_model().objects.create_superuser(
            username="relationship-history-manager"
        )
        self.client.force_login(actor)

        response = self.client.get(
            reverse("people:relationships", args=(self.person.pk,))
        )

        self.assertContains(response, "Bohdan Novák")
        self.assertContains(response, "Historická Osoba")
        for relationship in (
            archived_relationship,
            active_with_archived_person,
        ):
            self.assertNotContains(
                response,
                reverse(
                    "people:relationship-edit",
                    args=(self.person.pk, relationship.pk),
                ),
            )

        edit_url = reverse(
            "people:relationship-edit",
            args=(self.person.pk, archived_relationship.pk),
        )
        self.assertEqual(self.client.get(edit_url).status_code, 404)
        denied_post = self.client.post(edit_url, self.form_data(note="Změna"))
        self.assertEqual(denied_post.status_code, 404)
        archived_relationship.refresh_from_db()
        self.assertEqual(archived_relationship.note, "")

    def test_use_cases_enforce_access_and_global_lock_order(self) -> None:
        actor = self.editor("relationship-lock-order")
        lock_models: list[str] = []
        original_select_for_update = QuerySet.select_for_update

        def record_lock(queryset, *args, **kwargs):
            lock_models.append(queryset.model._meta.label)
            return original_select_for_update(queryset, *args, **kwargs)

        with patch.object(QuerySet, "select_for_update", record_lock):
            relationship = create_person_relationship(
                person=self.person,
                other_person_id=self.other.pk,
                relationship_kind="partner",
                data=PersonRelationshipInput(),
                actor=actor,
            )
        self.assertEqual(
            lock_models[:3],
            [
                "people.RelationshipType",
                "people.RelationshipType",
                "people.Person",
            ],
        )

        lock_models.clear()
        with patch.object(QuerySet, "select_for_update", record_lock):
            update_person_relationship(
                person=self.person,
                relationship=relationship,
                data=PersonRelationshipInput(note="Pořadí zámků"),
                actor=actor,
            )
        self.assertEqual(
            lock_models[:4],
            [
                "people.RelationshipType",
                "people.Relationship",
                "people.RelationshipType",
                "people.Person",
            ],
        )

        third = Person.objects.create(
            first_name="Restricted",
            access_level=AccessLevel.PUBLIC,
        )
        with self.assertRaises(PermissionDenied):
            create_person_relationship(
                person=self.person,
                other_person_id=third.pk,
                relationship_kind="child",
                data=PersonRelationshipInput(
                    access_level=AccessLevel.RESTRICTED
                ),
                actor=actor,
            )

    def test_csrf_and_unsupported_methods_do_not_write(self) -> None:
        actor = self.editor("relationship-csrf-editor")
        url = reverse(
            "people:relationship-create",
            args=(self.person.pk, "partner"),
        )
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(actor)

        csrf_denied = csrf_client.post(url, self.form_data())
        method_denied = self.client.put(url, self.form_data())

        self.assertEqual(csrf_denied.status_code, 403)
        self.assertEqual(method_denied.status_code, 405)
        self.assertFalse(Relationship.objects.exists())
