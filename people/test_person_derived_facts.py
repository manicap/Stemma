from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from common.choices import AccessLevel, DatePrecision, DateQualifier, Gender
from events.models import Event, EventParticipant, EventType, ParticipantRole

from .derived_selectors import get_visible_person_presentations
from .models import Person


class VisiblePersonDerivedFactsTests(TestCase):
    def setUp(self) -> None:
        self.birth_type = EventType.objects.get(code="birth")
        self.death_type = EventType.objects.get(code="death")
        self.born_role = ParticipantRole.objects.get(code="born_person")
        self.deceased_role = ParticipantRole.objects.get(
            code="deceased_person"
        )

    def create_person(self, first_name="Jan", last_name="Novák", **values):
        return Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            **values,
        )

    def create_life_event(
        self,
        person: Person,
        *,
        kind: str,
        access_level: str = AccessLevel.PUBLIC,
        date_precision: str = DatePrecision.EXACT,
        date_qualifier: str = DateQualifier.NONE,
        start_year: int | None = 1900,
        start_month: int | None = 1,
        start_day: int | None = 1,
        role: ParticipantRole | None = None,
        **values,
    ) -> Event:
        event = Event.objects.create(
            event_type=self.birth_type if kind == "birth" else self.death_type,
            access_level=access_level,
            date_precision=date_precision,
            date_qualifier=date_qualifier,
            start_year=start_year,
            start_month=start_month,
            start_day=start_day,
            **values,
        )
        EventParticipant.objects.create(
            event=event,
            person=person,
            role=(
                role
                or (
                    self.born_role
                    if kind == "birth"
                    else self.deceased_role
                )
            ),
        )
        return event

    def presentations(self, actor=None, *, as_of=date(2026, 8, 17)):
        return get_visible_person_presentations(
            actor=actor or AnonymousUser(),
            as_of=as_of,
        )

    def facts_for(self, person: Person, actor=None, **values):
        return next(
            presentation.facts
            for presentation in self.presentations(actor, **values)
            if presentation.person.pk == person.pk
        )

    def test_exact_birth_derives_living_status_date_and_age(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            start_year=2000,
            start_month=8,
            start_day=17,
        )

        facts = self.facts_for(person)

        self.assertEqual(facts.birth_text, "17. 8. 2000")
        self.assertIsNone(facts.death_text)
        self.assertFalse(facts.is_deceased)
        self.assertEqual(facts.age, 26)
        self.assertEqual(facts.age_text, "26 let")

    def test_deceased_age_uses_exact_visible_death(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            start_year=1900,
            start_month=5,
            start_day=10,
        )
        self.create_life_event(
            person,
            kind="death",
            start_year=1980,
            start_month=5,
            start_day=9,
        )

        facts = self.facts_for(person)

        self.assertTrue(facts.is_deceased)
        self.assertEqual(facts.death_text, "9. 5. 1980")
        self.assertEqual(facts.age_text, "79 let")

    def test_partial_date_only_derives_reliable_age(self) -> None:
        reliable = self.create_person("Spolehlivý", "Rok")
        ambiguous = self.create_person("Neurčitý", "Rok")
        for person in (reliable, ambiguous):
            self.create_life_event(
                person,
                kind="birth",
                date_precision=DatePrecision.YEAR,
                start_year=2000,
                start_month=None,
                start_day=None,
            )

        reliable_facts = self.facts_for(
            reliable,
            as_of=date(2026, 12, 31),
        )
        ambiguous_facts = self.facts_for(
            ambiguous,
            as_of=date(2026, 8, 17),
        )

        self.assertEqual(reliable_facts.birth_text, "2000")
        self.assertEqual(reliable_facts.age, 26)
        self.assertIsNone(ambiguous_facts.age)

    def test_qualified_date_is_shown_but_never_used_for_age(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            date_qualifier=DateQualifier.APPROXIMATE,
            start_year=2000,
        )

        facts = self.facts_for(person)

        self.assertEqual(facts.birth_text, "asi 1. 1. 2000")
        self.assertIsNone(facts.age_text)

    def test_month_date_is_formatted_and_can_produce_reliable_age(
        self,
    ) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            date_precision=DatePrecision.MONTH,
            start_year=2000,
            start_month=3,
            start_day=None,
        )

        facts = self.facts_for(person, as_of=date(2026, 12, 31))

        self.assertEqual(facts.birth_text, "3/2000")
        self.assertEqual(facts.age_text, "26 let")

    def test_range_is_formatted_but_ambiguous_age_is_not_shown(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            date_precision=DatePrecision.RANGE,
            start_year=1999,
            start_month=1,
            start_day=1,
            end_year=2000,
            end_month=12,
            end_day=31,
        )

        facts = self.facts_for(person)

        self.assertEqual(facts.birth_text, "1. 1. 1999–31. 12. 2000")
        self.assertIsNone(facts.age_text)

    def test_before_and_after_dates_are_shown_but_not_used_for_age(
        self,
    ) -> None:
        before = self.create_person("Před", "Datem")
        after = self.create_person("Po", "Datu")
        self.create_life_event(
            before,
            kind="birth",
            date_qualifier=DateQualifier.BEFORE,
            start_year=2000,
        )
        self.create_life_event(
            after,
            kind="birth",
            date_qualifier=DateQualifier.AFTER,
            start_year=2000,
        )

        before_facts = self.facts_for(before)
        after_facts = self.facts_for(after)

        self.assertEqual(before_facts.birth_text, "před 1. 1. 2000")
        self.assertEqual(after_facts.birth_text, "po 1. 1. 2000")
        self.assertIsNone(before_facts.age_text)
        self.assertIsNone(after_facts.age_text)

    def test_visible_death_without_date_still_marks_person_deceased(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="death",
            date_precision=DatePrecision.UNKNOWN,
            start_year=None,
            start_month=None,
            start_day=None,
        )

        facts = self.facts_for(person)

        self.assertTrue(facts.is_deceased)
        self.assertIsNone(facts.death_text)
        self.assertIsNone(facts.age)

    def test_hidden_life_events_do_not_affect_anonymous_facts(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="birth",
            access_level=AccessLevel.AUTHENTICATED,
            start_year=1900,
        )
        self.create_life_event(
            person,
            kind="death",
            access_level=AccessLevel.RESTRICTED,
            start_year=1980,
        )

        anonymous_facts = self.facts_for(person)
        actor = get_user_model().objects.create_user(username="reader")
        authenticated_facts = self.facts_for(person, actor)

        self.assertIsNone(anonymous_facts.birth_text)
        self.assertFalse(anonymous_facts.is_deceased)
        self.assertEqual(authenticated_facts.birth_text, "1. 1. 1900")
        self.assertFalse(authenticated_facts.is_deceased)

    def test_restricted_death_is_visible_only_with_current_permission(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="death",
            access_level=AccessLevel.RESTRICTED,
            start_year=1980,
        )
        actor = get_user_model().objects.create_user(username="elevated")
        permission = Permission.objects.get(
            content_type__app_label="accounts",
            codename="view_restricted_content",
        )
        actor.user_permissions.add(permission)
        self.assertTrue(self.facts_for(person, actor).is_deceased)

        get_user_model().objects.filter(pk=actor.pk).update(is_active=False)

        self.assertFalse(self.facts_for(person, actor).is_deceased)

    def test_archived_deleted_and_wrong_role_events_are_ignored(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="death",
            archived_at="2026-08-17T12:00:00Z",
        )
        self.create_life_event(
            person,
            kind="death",
            deleted_at="2026-08-17T12:00:00Z",
        )
        self.create_life_event(
            person,
            kind="death",
            role=self.born_role,
        )

        facts = self.facts_for(person)

        self.assertFalse(facts.is_deceased)

    def test_duplicate_visible_events_do_not_choose_arbitrary_date_or_age(
        self,
    ) -> None:
        person = self.create_person()
        self.create_life_event(person, kind="birth", start_year=1900)
        self.create_life_event(person, kind="birth", start_year=1901)
        self.create_life_event(person, kind="death", start_year=1980)
        self.create_life_event(person, kind="death", start_year=1981)

        facts = self.facts_for(person)

        self.assertIsNone(facts.birth_text)
        self.assertIsNone(facts.death_text)
        self.assertTrue(facts.is_deceased)
        self.assertIsNone(facts.age)

    def test_roman_suffix_uses_visible_cohort_birth_order_and_unknown_last(
        self,
    ) -> None:
        middle = self.create_person()
        oldest = self.create_person()
        unknown = self.create_person()
        self.create_life_event(middle, kind="birth", start_year=1950)
        self.create_life_event(oldest, kind="birth", start_year=1900)

        presentations = self.presentations()
        suffixes = {
            item.person.pk: item.facts.roman_suffix
            for item in presentations
        }

        self.assertEqual(suffixes[oldest.pk], "I.")
        self.assertEqual(suffixes[middle.pk], "II.")
        self.assertEqual(suffixes[unknown.pk], "III.")

    def test_hidden_namesake_does_not_create_gap_or_suffix(self) -> None:
        visible = self.create_person()
        self.create_person(access_level=AccessLevel.RESTRICTED)

        facts = self.facts_for(visible)

        self.assertIsNone(facts.roman_suffix)

    def test_exact_name_pair_defines_cohort_without_normalization(self) -> None:
        first = self.create_person("Jan", "Novák")
        second = self.create_person("jan", "Novák")

        self.assertIsNone(self.facts_for(first).roman_suffix)
        self.assertIsNone(self.facts_for(second).roman_suffix)

    def test_roman_tie_is_stably_resolved_by_primary_key(self) -> None:
        first = self.create_person()
        second = self.create_person()
        self.create_life_event(first, kind="birth", start_year=1900)
        self.create_life_event(second, kind="birth", start_year=1900)

        self.assertEqual(self.facts_for(first).roman_suffix, "I.")
        self.assertEqual(self.facts_for(second).roman_suffix, "II.")

    def test_query_count_is_constant_for_larger_visible_cohort(self) -> None:
        actor = get_user_model().objects.create_user(username="query-reader")
        self.create_person("První", "Osoba")
        with CaptureQueriesContext(connection) as small_context:
            self.presentations(actor)

        for index in range(12):
            self.create_person(f"Osoba {index}", "Test")
        with CaptureQueriesContext(connection) as large_context:
            self.presentations(actor)

        self.assertEqual(len(small_context), len(large_context))


class PersonDerivedFactsWebTests(VisiblePersonDerivedFactsTests):
    def test_list_and_detail_render_visible_derived_facts(self) -> None:
        older = self.create_person(gender=Gender.MALE)
        younger = self.create_person(gender=Gender.MALE)
        self.create_life_event(older, kind="birth", start_year=1900)
        self.create_life_event(older, kind="death", start_year=1980)
        self.create_life_event(younger, kind="birth", start_year=1950)

        response = self.client.get(f"/osoby/{older.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jan Novák I.", count=2)
        self.assertContains(response, "Narození:</strong> 1. 1. 1900")
        self.assertContains(response, "Úmrtí:</strong> 1. 1. 1980")
        self.assertContains(response, "Zemřelá osoba")
        self.assertContains(response, "80 let")

    def test_htmx_detail_does_not_leak_hidden_death(self) -> None:
        person = self.create_person()
        self.create_life_event(
            person,
            kind="death",
            access_level=AccessLevel.RESTRICTED,
            start_year=1980,
        )

        response = self.client.get(
            f"/osoby/{person.pk}/",
            headers={"HX-Request": "true"},
        )

        self.assertContains(response, "Žijící osoba")
        self.assertNotContains(response, "1980")

    def test_htmx_rename_recalculates_old_and_new_visible_cohorts(
        self,
    ) -> None:
        renamed = self.create_person("Jan", "Novák")
        remaining = self.create_person("Jan", "Novák")
        existing = self.create_person("Josef", "Dvořák")
        editor = get_user_model().objects.create_user(username="editor")
        editor.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="people",
                codename="change_person",
            )
        )
        self.client.force_login(editor)

        response = self.client.post(
            f"/osoby/{renamed.pk}/upravit/",
            {
                "first_name": "Josef",
                "last_name": "Dvořák",
                "gender": Gender.UNKNOWN,
                "category": "",
                "notes": "",
            },
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Josef Dvořák I.", count=2)
        self.assertContains(response, "Josef Dvořák II.")
        self.assertContains(response, f'person-list-item-{remaining.pk}')
        self.assertContains(response, f'person-list-item-{existing.pk}')
        self.assertContains(response, "Jan Novák</strong>")
        self.assertNotContains(response, "Jan Novák I.")
        self.assertNotContains(response, "Jan Novák II.")
