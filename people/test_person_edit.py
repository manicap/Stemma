from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel, Gender, VerificationStatus

from .models import Person, PersonCategory
from .services import PersonInput, update_person


class PersonUpdateServiceTests(TestCase):
    def create_editor(self, username: str = "service-editor"):
        editor = get_user_model().objects.create_user(username=username)
        editor.groups.add(Group.objects.get(name="Editor"))
        return editor

    def test_update_normalizes_fields_and_preserves_technical_metadata(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(username="creator")
        person = Person.objects.create(
            first_name="Původní",
            created_by=creator,
            access_level=AccessLevel.AUTHENTICATED,
            verification_status=VerificationStatus.PROBABLE,
        )
        category = PersonCategory.objects.get(code="direct_family")
        editor = self.create_editor()

        updated = update_person(
            person=person,
            data=PersonInput(
                category=category,
                gender=Gender.FEMALE,
                first_name="  Anna ",
                last_name=" Nováková  ",
                notes=" Poznámka. ",
                access_level=AccessLevel.RESTRICTED,
                verification_status=VerificationStatus.VERIFIED,
            ),
            actor=editor,
        )

        self.assertEqual(updated.first_name, "Anna")
        self.assertEqual(updated.last_name, "Nováková")
        self.assertEqual(updated.notes, "Poznámka.")
        self.assertEqual(updated.category, category)
        self.assertEqual(updated.created_by, creator)
        self.assertIsNone(updated.archived_at)
        self.assertEqual(updated.access_level, AccessLevel.AUTHENTICATED)
        self.assertEqual(
            updated.verification_status,
            VerificationStatus.PROBABLE,
        )

    def test_update_rejects_unsaved_missing_and_soft_deleted_person(self) -> None:
        missing = Person.objects.create(first_name="Chybějící")
        Person.objects.filter(pk=missing.pk).delete()
        editor = self.create_editor()

        for person in (Person(first_name="Neuložená"), missing):
            code = "person_unsaved"
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as context:
                    update_person(
                        person=person,
                        data=PersonInput(first_name="Změna"),
                        actor=editor,
                    )
                self.assertEqual(
                    context.exception.error_dict["person"][0].code,
                    code,
                )

    def test_invalid_update_rolls_back_without_partial_write(self) -> None:
        person = Person.objects.create(first_name="Původní")
        editor = self.create_editor()

        with self.assertRaises(ValidationError):
            update_person(
                person=person,
                data=PersonInput(),
                actor=editor,
            )

        person.refresh_from_db()
        self.assertEqual(person.first_name, "Původní")

    def test_update_rechecks_actor_and_current_target_security(self) -> None:
        editor = self.create_editor("revoked-editor")
        person = Person.objects.create(first_name="Původní")
        editor.groups.clear()

        with self.assertRaises(PermissionDenied):
            update_person(
                person=person,
                data=PersonInput(first_name="Zakázaná změna"),
                actor=editor,
            )

        editor.groups.add(Group.objects.get(name="Editor"))
        Person.objects.filter(pk=person.pk).update(
            access_level=AccessLevel.ADMIN_ONLY,
            verification_status=VerificationStatus.VERIFIED,
        )
        with self.assertRaises(Person.DoesNotExist):
            update_person(
                person=person,
                data=PersonInput(
                    first_name="Zakázaná změna",
                    access_level=AccessLevel.PUBLIC,
                    verification_status=VerificationStatus.UNCONFIRMED,
                ),
                actor=editor,
            )

        person.refresh_from_db()
        self.assertEqual(person.first_name, "Původní")
        self.assertEqual(person.access_level, AccessLevel.ADMIN_ONLY)
        self.assertEqual(
            person.verification_status,
            VerificationStatus.VERIFIED,
        )

        visible = Person.objects.create(
            first_name="Stále viditelná",
            verification_status=VerificationStatus.PROBABLE,
        )
        Person.objects.filter(pk=visible.pk).update(
            verification_status=VerificationStatus.VERIFIED,
        )
        updated = update_person(
            person=visible,
            data=PersonInput(
                first_name="Bezpečně změněná",
                verification_status=VerificationStatus.UNCONFIRMED,
            ),
            actor=editor,
        )
        self.assertEqual(updated.first_name, "Bezpečně změněná")
        self.assertEqual(
            updated.verification_status,
            VerificationStatus.VERIFIED,
        )

    def test_update_rejects_newly_archived_or_deleted_target(self) -> None:
        editor = self.create_editor("lifecycle-editor")
        for field_name in ("archived_at", "deleted_at"):
            person = Person.objects.create(first_name=field_name)
            Person.objects.filter(pk=person.pk).update(
                **{field_name: timezone.now()}
            )
            with self.subTest(field=field_name):
                with self.assertRaises(Person.DoesNotExist):
                    update_person(
                        person=person,
                        data=PersonInput(first_name="Zakázaná změna"),
                        actor=editor,
                    )


class PersonEditWebTests(TestCase):
    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            notes="Původní poznámka.",
            access_level=AccessLevel.PUBLIC,
            verification_status=VerificationStatus.PROBABLE,
        )
        self.hidden_person = Person.objects.create(
            first_name="Skrytá",
            access_level=AccessLevel.RESTRICTED,
        )

    def create_role_user(self, username: str, group_name: str):
        user = get_user_model().objects.create_user(
            username=username,
            password="test-password",
        )
        user.groups.add(Group.objects.get(name=group_name))
        return user

    def valid_data(self, **overrides: str) -> dict[str, str]:
        data = {
            "first_name": "Jana",
            "last_name": "Novotná",
            "gender": Gender.FEMALE,
            "category": "",
            "notes": "Aktualizovaná poznámka.",
        }
        data.update(overrides)
        return data

    def test_detail_shows_edit_action_only_with_permission(self) -> None:
        anonymous_response = self.client.get(
            reverse("people:detail", args=(self.person.pk,))
        )
        editor = self.create_role_user("editor", "Editor")
        self.client.force_login(editor)
        editor_response = self.client.get(
            reverse("people:detail", args=(self.person.pk,))
        )

        self.assertNotContains(anonymous_response, "Upravit osobu")
        self.assertContains(editor_response, "Upravit osobu")

    def test_editor_can_open_scoped_basic_form(self) -> None:
        editor = self.create_role_user("form-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.get(
            reverse("people:edit", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upravit základní údaje")
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="category"')
        self.assertNotContains(response, 'name="access_level"')
        self.assertNotContains(response, 'name="verification_status"')
        self.assertNotContains(response, "datum narození")
        self.assertContains(response, 'data-dirty="false"')
        self.assertContains(response, "Ukládám…")
        self.assertContains(response, "Pokračovat v úpravě")

    def test_htmx_edit_get_returns_only_form_fragment(self) -> None:
        editor = self.create_role_user("fragment-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.get(
            reverse("people:edit", args=(self.person.pk,)),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upravit základní údaje")
        self.assertNotContains(response, "<!doctype html>")

    def test_reader_cannot_open_or_submit_edit(self) -> None:
        reader = self.create_role_user("reader", "Čtenář")
        self.client.force_login(reader)
        url = reverse("people:edit", args=(self.person.pk,))

        get_response = self.client.get(url)
        post_response = self.client.post(url, self.valid_data())

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Anna")

    def test_anonymous_user_cannot_open_or_submit_edit(self) -> None:
        url = reverse("people:edit", args=(self.person.pk,))

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, self.valid_data()).status_code,
            403,
        )

    def test_inactive_editor_cannot_submit_edit(self) -> None:
        editor = self.create_role_user("inactive-editor", "Editor")
        self.client.force_login(editor)
        get_user_model().objects.filter(pk=editor.pk).update(is_active=False)

        response = self.client.post(
            reverse("people:edit", args=(self.person.pk,)),
            self.valid_data(),
        )

        self.assertEqual(response.status_code, 403)
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Anna")

    def test_editor_cannot_discover_or_edit_hidden_person(self) -> None:
        editor = self.create_role_user("hidden-editor", "Editor")
        self.client.force_login(editor)
        url = reverse("people:edit", args=(self.hidden_person.pk,))

        get_response = self.client.get(url)
        post_response = self.client.post(url, self.valid_data())

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(post_response.status_code, 404)
        self.hidden_person.refresh_from_db()
        self.assertEqual(self.hidden_person.first_name, "Skrytá")

    def test_valid_post_updates_through_service_and_preserves_security(self) -> None:
        editor = self.create_role_user("saving-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.post(
            reverse("people:edit", args=(self.person.pk,)),
            self.valid_data(
                access_level=AccessLevel.ADMIN_ONLY,
                verification_status=VerificationStatus.DISPUTED,
            ),
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("people:detail", args=(self.person.pk,)),
        )
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Jana")
        self.assertEqual(self.person.last_name, "Novotná")
        self.assertEqual(self.person.access_level, AccessLevel.PUBLIC)
        self.assertEqual(
            self.person.verification_status,
            VerificationStatus.PROBABLE,
        )
        self.assertContains(response, "Změny byly uloženy.")

    def test_htmx_save_updates_detail_and_list_without_full_reload(self) -> None:
        editor = self.create_role_user("htmx-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.post(
            reverse("people:edit", args=(self.person.pk,)),
            self.valid_data(),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:detail", args=(self.person.pk,)),
        )
        self.assertContains(response, "Změny byly uloženy.")
        self.assertContains(response, "Jana Novotná", count=2)
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertNotContains(response, "<!doctype html>")

    def test_invalid_post_keeps_values_and_shows_inline_error(self) -> None:
        editor = self.create_role_user("invalid-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.post(
            reverse("people:edit", args=(self.person.pk,)),
            self.valid_data(first_name="", last_name=""),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vyplňte alespoň jméno", count=4)
        self.assertContains(response, "Aktualizovaná poznámka.")
        self.assertContains(response, 'data-dirty="true"')
        self.assertContains(response, 'aria-invalid="true"', count=2)
        self.assertContains(response, "Formulář se nepodařilo uložit")
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Anna")

    def test_staff_with_edit_permission_still_cannot_edit_hidden_person(self) -> None:
        staff = get_user_model().objects.create_user(
            username="staff-editor",
            password="test-password",
            is_staff=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(codename="change_person")
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("people:edit", args=(self.hidden_person.pk,)),
            self.valid_data(),
        )

        self.assertEqual(response.status_code, 404)

    def test_administrator_and_superuser_can_edit_elevated_visible_people(
        self,
    ) -> None:
        administrator = self.create_role_user("administrator", "Správce")
        self.client.force_login(administrator)
        restricted_response = self.client.post(
            reverse("people:edit", args=(self.hidden_person.pk,)),
            self.valid_data(first_name="Správcem změněná"),
        )
        self.assertEqual(restricted_response.status_code, 302)

        admin_only = Person.objects.create(
            first_name="Pouze admin",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        superuser = get_user_model().objects.create_superuser(
            username="superuser",
            password="test-password",
        )
        self.client.force_login(superuser)
        superuser_response = self.client.post(
            reverse("people:edit", args=(admin_only.pk,)),
            self.valid_data(first_name="Super změna"),
        )
        self.assertEqual(superuser_response.status_code, 302)

    def test_archived_and_deleted_targets_stay_hidden_from_edit(self) -> None:
        administrator = self.create_role_user("lifecycle-admin", "Správce")
        self.client.force_login(administrator)
        for field_name in ("archived_at", "deleted_at"):
            person = Person.objects.create(first_name=field_name)
            Person.objects.filter(pk=person.pk).update(
                **{field_name: timezone.now()}
            )
            url = reverse("people:edit", args=(person.pk,))
            with self.subTest(field=field_name):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(
                    self.client.post(url, self.valid_data()).status_code,
                    404,
                )

    def test_delete_method_is_rejected_without_write(self) -> None:
        editor = self.create_role_user("method-editor", "Editor")
        self.client.force_login(editor)

        response = self.client.delete(
            reverse("people:edit", args=(self.person.pk,))
        )

        self.assertEqual(response.status_code, 405)
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Anna")

    def test_edit_post_requires_csrf_token(self) -> None:
        editor = self.create_role_user("csrf-editor", "Editor")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(editor)

        response = csrf_client.post(
            reverse("people:edit", args=(self.person.pk,)),
            self.valid_data(),
        )

        self.assertEqual(response.status_code, 403)
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, "Anna")
