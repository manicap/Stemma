from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import TestCase
from django.urls import reverse

from common.choices import AccessLevel, DatePrecision, Gender
from events.models import Event, EventParticipant, EventType, ParticipantRole

from .models import (
    NameType,
    Person,
    PersonCategory,
    PersonName,
    Relationship,
    RelationshipType,
)
from .search_selectors import (
    PERSON_SEARCH_QUERY_MAX_LENGTH,
    PERSON_SUGGESTION_LIMIT,
    get_visible_person_browser,
)


class PersonSearchTests(TestCase):
    def setUp(self) -> None:
        self.birth_type = EventType.objects.get(code="birth")
        self.born_role = ParticipantRole.objects.get(code="born_person")
        self.name_type = NameType.objects.create(
            code="search-alternative",
            name="Alternativní jméno",
        )
        self.family = PersonCategory.objects.create(
            code="search-family",
            name="Rodina",
        )
        self.friends = PersonCategory.objects.create(
            code="search-friends",
            name="Přátelé",
        )

    def create_birth(
        self,
        person: Person,
        *,
        year: int,
        precision: str = DatePrecision.YEAR,
        access_level: str = AccessLevel.PUBLIC,
    ) -> Event:
        event = Event.objects.create(
            event_type=self.birth_type,
            access_level=access_level,
            date_precision=precision,
            start_year=year,
            start_month=1 if precision == DatePrecision.EXACT else None,
            start_day=1 if precision == DatePrecision.EXACT else None,
        )
        EventParticipant.objects.create(
            event=event,
            person=person,
            role=self.born_role,
        )
        return event

    @staticmethod
    def person_ids(result) -> list[int]:
        return [item.person.pk for item in result.presentations]

    def test_search_matches_basic_and_visible_alternative_names_normalized(
        self,
    ) -> None:
        basic = Person.objects.create(first_name="Šárka", last_name="Černá")
        alternative = Person.objects.create(
            first_name="Marie",
            last_name="Nováková",
        )
        PersonName.objects.create(
            person=alternative,
            name_type=self.name_type,
            value="Mařenka Svobodová",
            normalized_value="marenka svobodova",
        )

        basic_result = get_visible_person_browser(
            actor=AnonymousUser(),
            query="SARKA cer",
        )
        alternative_result = get_visible_person_browser(
            actor=AnonymousUser(),
            query="RENKA svob",
        )

        self.assertEqual(self.person_ids(basic_result), [basic.pk])
        self.assertEqual(
            self.person_ids(alternative_result),
            [alternative.pk],
        )

        for index in range(PERSON_SUGGESTION_LIMIT + 2):
            Person.objects.create(first_name=f"Marie {index}")
        limited = get_visible_person_browser(
            actor=AnonymousUser(),
            query="Marie",
        )
        bounded = get_visible_person_browser(
            actor=AnonymousUser(),
            query="x" * (PERSON_SEARCH_QUERY_MAX_LENGTH + 50),
        )
        self.assertEqual(len(limited.suggestions), PERSON_SUGGESTION_LIMIT)
        self.assertEqual(
            len(bounded.query),
            PERSON_SEARCH_QUERY_MAX_LENGTH,
        )

    def test_autocomplete_never_leaks_hidden_person_or_hidden_name(self) -> None:
        public = Person.objects.create(first_name="Veřejná", last_name="Osoba")
        hidden = Person.objects.create(
            first_name="Neveřejná",
            last_name="Tajemství",
            access_level=AccessLevel.RESTRICTED,
        )
        PersonName.objects.create(
            person=public,
            name_type=self.name_type,
            value="Skrytá přezdívka",
            normalized_value="skryta prezdivka",
            access_level=AccessLevel.RESTRICTED,
        )

        response = self.client.get(
            reverse("people:search-results"),
            {"q": "tajemstvi"},
            HTTP_HX_REQUEST="true",
        )
        hidden_name_response = self.client.get(
            reverse("people:search-results"),
            {"q": "skryta prezdivka"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, hidden.first_name)
        self.assertNotContains(response, hidden.last_name)
        self.assertNotContains(hidden_name_response, public.first_name)
        self.assertContains(
            response,
            "Nebyla nalezena žádná odpovídající osoba.",
        )

    def test_category_search_and_name_sort_are_combined(self) -> None:
        Person.objects.create(
            first_name="Zdeněk",
            last_name="Ábel",
            category=self.friends,
        )
        expected_second = Person.objects.create(
            first_name="Adam",
            last_name="Černý",
            category=self.family,
        )
        expected_first = Person.objects.create(
            first_name="Žaneta",
            last_name="Bílá",
            category=self.family,
        )

        result = get_visible_person_browser(
            actor=AnonymousUser(),
            query="a",
            category=str(self.family.pk),
            sort="last_name_asc",
        )

        self.assertEqual(
            self.person_ids(result),
            [expected_first.pk, expected_second.pk],
        )
        self.friends.is_active = False
        self.friends.save(update_fields=("is_active",))
        inactive_result = get_visible_person_browser(actor=AnonymousUser())
        self.assertIn(self.friends, inactive_result.categories)

    def test_birth_sort_uses_visible_partial_dates_and_unknown_last(self) -> None:
        oldest = Person.objects.create(first_name="Oldřich")
        youngest = Person.objects.create(first_name="Jan")
        hidden_birth = Person.objects.create(first_name="Skryté narození")
        unknown = Person.objects.create(first_name="Bez narození")
        self.create_birth(oldest, year=1842)
        self.create_birth(youngest, year=2001, precision=DatePrecision.EXACT)
        self.create_birth(
            hidden_birth,
            year=2020,
            access_level=AccessLevel.RESTRICTED,
        )

        youngest_result = get_visible_person_browser(
            actor=AnonymousUser(),
            sort="youngest",
        )
        oldest_result = get_visible_person_browser(
            actor=AnonymousUser(),
            sort="oldest",
        )
        year_result = get_visible_person_browser(
            actor=AnonymousUser(),
            query="1842",
        )
        hidden_year_result = get_visible_person_browser(
            actor=AnonymousUser(),
            query="2020",
        )

        self.assertEqual(
            self.person_ids(youngest_result),
            [youngest.pk, oldest.pk, unknown.pk, hidden_birth.pk],
        )
        self.assertEqual(
            self.person_ids(oldest_result),
            [oldest.pk, youngest.pk, unknown.pk, hidden_birth.pk],
        )
        self.assertEqual(self.person_ids(year_result), [oldest.pk])
        self.assertEqual(self.person_ids(hidden_year_result), [])

    def test_htmx_results_open_detail_and_preserve_browser_context(self) -> None:
        person = Person.objects.create(
            first_name="Božena",
            last_name="Němcová",
            category=self.family,
        )
        query = {
            "q": "bozena",
            "category": str(self.family.pk),
            "sort": "first_name_desc",
        }

        response = self.client.get(
            reverse("people:search-results"),
            query,
            HTTP_HX_REQUEST="true",
        )
        detail_response = self.client.get(
            reverse("people:detail", args=(person.pk,)),
            query,
            HTTP_HX_REQUEST="true",
        )

        self.assertContains(response, 'id="person-browser-results"')
        self.assertContains(response, 'role="option"')
        self.assertContains(
            response,
            reverse("people:detail", args=(person.pk,)),
        )
        self.assertContains(detail_response, "Božena Němcová")
        self.assertContains(
            detail_response,
            "q=bozena&amp;category=" + str(self.family.pk),
        )

    def test_empty_result_offers_create_only_with_current_permission(self) -> None:
        anonymous_response = self.client.get(
            reverse("people:search-results"),
            {"q": "nenalezeno"},
        )
        actor = get_user_model().objects.create_user(
            username="search-editor",
            password="test-password",
        )
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="add_person",
            )
        )
        self.client.force_login(actor)
        editor_response = self.client.get(
            reverse("people:search-results"),
            {"q": "nenalezeno"},
        )

        self.assertContains(
            anonymous_response,
            "Nebyla nalezena žádná odpovídající osoba.",
        )
        self.assertNotContains(anonymous_response, "+ Přidat novou osobu")
        self.assertContains(editor_response, "+ Přidat novou osobu")

    def test_filtered_relationship_link_keeps_object_authorization(self) -> None:
        source = Person.objects.create(
            first_name="Zdroj",
            category=self.family,
        )
        related = Person.objects.create(
            first_name="Příbuzný",
            category=self.friends,
        )
        relationship_type = RelationshipType.objects.first()
        Relationship.objects.create(
            relationship_type=relationship_type,
            person_a=source,
            person_b=related,
        )

        response = self.client.get(
            reverse("people:relationships", args=(source.pk,)),
            {"category": str(self.family.pk)},
        )

        self.assertContains(
            response,
            reverse("people:detail", args=(related.pk,))
            + f"?category={self.family.pk}",
        )

    def test_edit_replaces_filtered_browser_and_preserves_fallback_url(self) -> None:
        person = Person.objects.create(
            first_name="Adam",
            last_name="Filtrovaný",
            category=self.family,
        )
        actor = get_user_model().objects.create_user(
            username="search-person-editor",
            password="test-password",
        )
        actor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )
        self.client.force_login(actor)
        url = reverse("people:edit", args=(person.pk,))
        query = f"?category={self.family.pk}&sort=last_name_asc"
        data = {
            "first_name": "Adam",
            "last_name": "Filtrovaný",
            "gender": Gender.UNKNOWN,
            "category": self.friends.pk,
            "notes": "",
        }

        htmx_response = self.client.post(
            url + query,
            data,
            HTTP_HX_REQUEST="true",
        )
        person.category = self.family
        person.save(update_fields=("category",))
        fallback_response = self.client.post(url + query, data)

        self.assertContains(
            htmx_response,
            'hx-swap-oob="outerHTML"',
        )
        self.assertNotContains(
            htmx_response,
            f'id="person-list-item-{person.pk}"',
        )
        self.assertEqual(fallback_response.status_code, 302)
        self.assertIn(
            f"category={self.family.pk}&sort=last_name_asc",
            fallback_response.headers["Location"],
        )
