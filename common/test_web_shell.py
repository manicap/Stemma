from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from common.choices import AccessLevel
from people.models import Person


class ApplicationShellWebTests(TestCase):
    def setUp(self) -> None:
        self.public_person = Person.objects.create(
            first_name="Anna",
            last_name="Nováková",
            access_level=AccessLevel.PUBLIC,
        )
        self.hidden_person = Person.objects.create(
            first_name="Skrytá",
            last_name="Osoba",
            access_level=AccessLevel.RESTRICTED,
        )

    def test_overview_owns_root_and_people_keep_their_section(self) -> None:
        self.assertEqual(reverse("common:overview"), "/")
        self.assertEqual(reverse("people:index"), "/osoby/")
        self.assertEqual(
            reverse("people:detail", args=(self.public_person.pk,)),
            f"/osoby/{self.public_person.pk}/",
        )

    def test_overview_uses_only_actor_visible_real_people(self) -> None:
        response = self.client.get(reverse("common:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dostupná data")
        self.assertContains(response, "Anna Nováková")
        self.assertContains(response, "Dostupné osoby: 1", html=False)
        self.assertNotContains(response, "Skrytá Osoba")

    def test_empty_overview_has_honest_empty_and_planned_states(self) -> None:
        Person.objects.all().delete()

        response = self.client.get(reverse("common:overview"))

        self.assertContains(
            response,
            "Zatím zde nejsou žádné osoby, které můžete zobrazit.",
        )
        self.assertContains(response, "Plánovaná oblast", count=4)
        self.assertContains(response, 'aria-disabled="true"', count=5)

    def test_global_navigation_is_stable_and_marks_active_section(self) -> None:
        overview_response = self.client.get(reverse("common:overview"))
        people_response = self.client.get(reverse("people:index"))

        for response in (overview_response, people_response):
            self.assertContains(response, 'aria-label="Hlavní navigace"')
            self.assertContains(response, ">Přehled</span>", html=False)
            self.assertContains(response, ">Osoby</span>", html=False)
            self.assertContains(response, "Rodokmen")
            self.assertContains(response, "Dokumenty")
            self.assertContains(response, "Místa")
            self.assertContains(response, "Materiály / zdroje")
            self.assertContains(response, "Můj prostor")
        self.assertContains(
            overview_response,
            f'href="{reverse("common:overview")}" aria-current="page"',
        )
        self.assertContains(
            people_response,
            f'href="{reverse("people:index")}" aria-current="page"',
        )

    def test_dark_is_default_but_local_preference_can_override_it(self) -> None:
        response = self.client.get(reverse("common:overview"))

        self.assertContains(response, '<html lang="cs" data-theme="dark">')
        self.assertContains(response, 'localStorage.getItem("stemma-theme")')
        self.assertContains(response, "storedTheme === \"light\"")

    def test_authenticated_overview_identifies_member_without_fake_space(
        self,
    ) -> None:
        actor = get_user_model().objects.create_user(
            username="member",
            first_name="Demo",
            last_name="Člen",
        )
        self.client.force_login(actor)

        response = self.client.get(reverse("common:overview"))

        self.assertContains(response, "Přihlášený člen:")
        self.assertContains(response, "Demo Člen")
        self.assertContains(
            response,
            "Osobní pracovní prostor bude doplněn později.",
        )

    def test_overview_preview_changes_with_actor_visibility(self) -> None:
        administrator = get_user_model().objects.create_superuser(
            username="administrator",
            password="test-password",
        )
        self.client.force_login(administrator)

        response = self.client.get(reverse("common:overview"))

        self.assertContains(response, self.public_person.first_name)
        self.assertContains(response, self.hidden_person.first_name)
        self.assertContains(response, "Dostupné osoby: 2", html=False)

    def test_overview_rejects_unsafe_http_methods(self) -> None:
        self.assertEqual(
            self.client.post(reverse("common:overview")).status_code,
            405,
        )
