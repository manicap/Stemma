from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from common.choices import AccessLevel, Gender

from .models import Person, PersonCategory


class PersonCreateWebTests(TestCase):
    def create_actor(self, username: str = "person-creator"):
        actor = get_user_model().objects.create_user(
            username=username,
            password="test-password",
        )
        actor.groups.add(Group.objects.get(name="Editor"))
        return actor

    def valid_data(self, **overrides: str) -> dict[str, str]:
        data = {
            "title_before_name": "Ing.",
            "first_name": "Anna",
            "last_name": "Nováková",
            "title_after_name": "Ph.D.",
            "gender": Gender.FEMALE,
            "category": PersonCategory.objects.get(
                code="direct_family"
            ).pk,
            "notes": "Nově založená osoba.",
            "access_level": AccessLevel.AUTHENTICATED,
        }
        data.update(overrides)
        return data

    def test_add_action_and_form_require_add_person_permission(self) -> None:
        anonymous_index = self.client.get(reverse("people:index"))
        actor = self.create_actor()
        self.client.force_login(actor)

        permitted_index = self.client.get(reverse("people:index"))
        form_response = self.client.get(
            reverse("people:create"),
            headers={"HX-Request": "true"},
        )

        self.assertNotContains(anonymous_index, "+ Přidat osobu")
        self.assertContains(permitted_index, "+ Přidat osobu")
        self.assertEqual(form_response.status_code, 200)
        self.assertTemplateUsed(
            form_response,
            "people/partials/person_create_form.html",
        )
        self.assertContains(form_response, "Uložit osobu")
        self.assertNotContains(form_response, "<!doctype html>")

    def test_authorized_post_creates_person_through_approved_fields(self) -> None:
        actor = self.create_actor("saving-creator")
        self.client.force_login(actor)

        response = self.client.post(
            reverse("people:create"),
            self.valid_data(),
        )

        person = Person.objects.get()
        self.assertRedirects(
            response,
            reverse("people:detail", args=(person.pk,)),
        )
        self.assertEqual(person.created_by, actor)
        self.assertEqual(person.first_name, "Anna")
        self.assertEqual(person.last_name, "Nováková")
        self.assertEqual(person.title_before_name, "Ing.")
        self.assertEqual(person.title_after_name, "Ph.D.")
        self.assertEqual(person.notes, "Nově založená osoba.")
        self.assertEqual(person.access_level, AccessLevel.AUTHENTICATED)

    def test_unauthorized_and_inactive_direct_posts_do_not_write(self) -> None:
        url = reverse("people:create")

        anonymous_response = self.client.post(url, self.valid_data())
        actor = self.create_actor("inactive-creator")
        self.client.force_login(actor)
        get_user_model().objects.filter(pk=actor.pk).update(is_active=False)
        inactive_response = self.client.post(url, self.valid_data())

        self.assertEqual(anonymous_response.status_code, 403)
        self.assertEqual(inactive_response.status_code, 403)
        self.assertFalse(Person.objects.exists())

    def test_invalid_identity_keeps_values_and_creates_nothing(self) -> None:
        actor = self.create_actor("invalid-creator")
        self.client.force_login(actor)

        response = self.client.post(
            reverse("people:create"),
            self.valid_data(first_name="", last_name=""),
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vyplňte alespoň jméno", count=4)
        self.assertContains(response, "Osobu se nepodařilo uložit")
        self.assertContains(response, 'aria-invalid="true"', count=2)
        self.assertContains(response, 'data-dirty="true"')
        self.assertFalse(Person.objects.exists())

    def test_htmx_success_updates_selected_detail_and_complete_list(self) -> None:
        existing = Person.objects.create(first_name="Bohumil")
        actor = self.create_actor("htmx-creator")
        self.client.force_login(actor)

        response = self.client.post(
            reverse("people:create"),
            self.valid_data(),
            headers={"HX-Request": "true"},
        )

        created = Person.objects.exclude(pk=existing.pk).get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["HX-Push-Url"],
            reverse("people:detail", args=(created.pk,)),
        )
        self.assertContains(response, "Osoba byla vytvořena.")
        self.assertContains(response, "Anna Nováková", count=2)
        self.assertContains(response, "Bohumil")
        self.assertContains(response, 'id="person-list"')
        self.assertContains(response, 'hx-swap-oob="outerHTML"')
        self.assertNotContains(response, "<!doctype html>")

    def test_access_choices_and_post_fail_closed_for_unavailable_level(self) -> None:
        actor = self.create_actor("access-creator")
        self.client.force_login(actor)

        form_response = self.client.get(reverse("people:create"))
        post_response = self.client.post(
            reverse("people:create"),
            self.valid_data(access_level=AccessLevel.ADMIN_ONLY),
            headers={"HX-Request": "true"},
        )

        self.assertContains(
            form_response,
            f'value="{AccessLevel.AUTHENTICATED}"',
        )
        self.assertNotContains(
            form_response,
            f'value="{AccessLevel.RESTRICTED}"',
        )
        self.assertNotContains(
            form_response,
            f'value="{AccessLevel.ADMIN_ONLY}"',
        )
        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "Vyberte platnou možnost")
        self.assertFalse(Person.objects.exists())
