from dataclasses import FrozenInstanceError, fields, is_dataclass
from inspect import Parameter, signature

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision

from . import selectors
from .models import Person, Relationship, RelationshipType
from .selectors import SiblingOverviewItem, get_sibling_overview


class SiblingOverviewApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu agregovaného selectoru."""

    def test_module_exports_exact_public_api(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "RelationshipOverviewItem",
                "RelationshipOverviewReason",
                "SiblingOverviewItem",
                "get_biological_siblings",
                "get_relationship_overview",
                "get_sibling_overview",
                "get_visible_people",
                "get_visible_person",
                "get_visible_relationship_overview",
            ),
        )

    def test_item_is_frozen_slotted_dataclass_with_exact_fields(self) -> None:
        item = SiblingOverviewItem(
            person=Person(first_name="Test"),
            relationship_codes=("biological",),
        )

        self.assertTrue(is_dataclass(SiblingOverviewItem))
        self.assertEqual(
            tuple(field.name for field in fields(SiblingOverviewItem)),
            ("person", "relationship_codes"),
        )
        self.assertFalse(hasattr(item, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            item.relationship_codes = ("sibling",)

    def test_function_uses_keyword_only_person(self) -> None:
        parameters = signature(get_sibling_overview).parameters

        self.assertEqual(tuple(parameters), ("person",))
        self.assertIs(
            parameters["person"].kind,
            Parameter.KEYWORD_ONLY,
        )


class SiblingOverviewSelectorTests(TestCase):
    """Ověření agregace všech schválených sourozeneckých důvodů."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.relationship_types = {
            relationship_type.code: relationship_type
            for relationship_type in RelationshipType.objects.all()
        }

    def create_person(
        self,
        first_name: str,
        *,
        last_name: str = "Testovací",
        access_level: str = AccessLevel.PUBLIC,
    ) -> Person:
        return Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            access_level=access_level,
        )

    def create_relationship(
        self,
        code: str,
        person_a: Person,
        person_b: Person,
        **values,
    ) -> Relationship:
        return Relationship.objects.create(
            relationship_type=self.relationship_types[code],
            person_a=person_a,
            person_b=person_b,
            **values,
        )

    def create_biological_pair(
        self,
        *,
        prefix: str,
    ) -> tuple[Person, Person, Person]:
        parent = self.create_person(f"{prefix} rodič")
        person = self.create_person(f"{prefix} osoba")
        sibling = self.create_person(f"{prefix} sourozenec")
        self.create_relationship("biological_parent", parent, person)
        self.create_relationship("biological_parent", parent, sibling)
        return parent, person, sibling

    def test_returns_tuple_of_items(self) -> None:
        person = self.create_person("Tuple A")
        sibling = self.create_person("Tuple B")
        self.create_relationship("sibling", person, sibling)

        result = get_sibling_overview(person=person)

        self.assertIsInstance(result, tuple)
        self.assertTrue(result)
        self.assertTrue(
            all(isinstance(item, SiblingOverviewItem) for item in result)
        )

    def test_only_biological_reason(self) -> None:
        _, person, sibling = self.create_biological_pair(prefix="Biologický")

        self.assertEqual(
            get_sibling_overview(person=person),
            (
                SiblingOverviewItem(
                    person=sibling,
                    relationship_codes=("biological",),
                ),
            ),
        )

    def test_each_explicit_sibling_type_returns_its_reason(self) -> None:
        for index, code in enumerate(
            (
                "sibling",
                "adoptive_sibling",
                "step_sibling",
                "social_sibling",
            )
        ):
            with self.subTest(code=code):
                person = self.create_person(f"Explicitní A {index}")
                sibling = self.create_person(f"Explicitní B {index}")
                self.create_relationship(code, person, sibling)

                self.assertEqual(
                    get_sibling_overview(person=person),
                    (
                        SiblingOverviewItem(
                            person=sibling,
                            relationship_codes=(code,),
                        ),
                    ),
                )

    def test_explicit_relationship_is_read_from_both_sides(self) -> None:
        person_a = self.create_person("Strana A")
        person_b = self.create_person("Strana B")
        self.create_relationship("sibling", person_a, person_b)

        self.assertEqual(
            get_sibling_overview(person=person_a)[0].person,
            person_b,
        )
        self.assertEqual(
            get_sibling_overview(person=person_b)[0].person,
            person_a,
        )

    def test_all_five_reasons_are_merged_in_stable_order(self) -> None:
        _, person, sibling = self.create_biological_pair(prefix="Všechny")
        for code in reversed(
            (
                "sibling",
                "adoptive_sibling",
                "step_sibling",
                "social_sibling",
            )
        ):
            self.create_relationship(code, person, sibling)

        self.assertEqual(
            get_sibling_overview(person=person),
            (
                SiblingOverviewItem(
                    person=sibling,
                    relationship_codes=(
                        "biological",
                        "sibling",
                        "adoptive_sibling",
                        "step_sibling",
                        "social_sibling",
                    ),
                ),
            ),
        )

    def test_multiple_periods_create_one_reason(self) -> None:
        person = self.create_person("Období A")
        sibling = self.create_person("Období B")
        for year in (1900, 1950):
            self.create_relationship(
                "sibling",
                person,
                sibling,
                date_precision=DatePrecision.EXACT,
                start_year=year,
                start_month=1,
                start_day=1,
            )

        self.assertEqual(
            get_sibling_overview(person=person)[0].relationship_codes,
            ("sibling",),
        )

    def test_multiple_people_keep_their_reasons_and_exclude_input(self) -> None:
        person = self.create_person("Vstup")
        sibling = self.create_person("Obecný")
        adoptive = self.create_person("Adoptivní")
        self.create_relationship("sibling", person, sibling)
        self.create_relationship("adoptive_sibling", person, adoptive)

        result = get_sibling_overview(person=person)
        reasons_by_id = {
            item.person.pk: item.relationship_codes for item in result
        }

        self.assertEqual(
            reasons_by_id,
            {
                sibling.pk: ("sibling",),
                adoptive.pk: ("adoptive_sibling",),
            },
        )
        self.assertNotIn(person.pk, reasons_by_id)

    def test_types_outside_scope_do_not_create_results(self) -> None:
        person = self.create_person("Mimo rozsah A")
        excluded_codes = (
            "biological_parent",
            "adoptive_parent",
            "step_parent",
            "foster_parent",
            "guardian",
            "spouse",
            "partner",
            "godparent",
            "family_friend",
            "other",
        )
        for index, code in enumerate(excluded_codes):
            other = self.create_person(f"Mimo rozsah B {index}")
            self.create_relationship(code, person, other)

        self.assertEqual(get_sibling_overview(person=person), ())

    def test_explicit_relationship_lifecycle_rules(self) -> None:
        archived_person = self.create_person("Archivovaná vazba A")
        archived_sibling = self.create_person("Archivovaná vazba B")
        archived = self.create_relationship(
            "sibling",
            archived_person,
            archived_sibling,
        )
        Relationship.objects.filter(pk=archived.pk).update(
            archived_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=archived_person)[0].person,
            archived_sibling,
        )

        deleted_person = self.create_person("Odstraněná vazba A")
        deleted_sibling = self.create_person("Odstraněná vazba B")
        deleted = self.create_relationship(
            "sibling",
            deleted_person,
            deleted_sibling,
        )
        Relationship.objects.filter(pk=deleted.pk).update(
            deleted_at=timezone.now(),
        )
        self.assertEqual(get_sibling_overview(person=deleted_person), ())

        inactive_person = self.create_person("Neaktivní typ A")
        inactive_sibling = self.create_person("Neaktivní typ B")
        self.create_relationship(
            "social_sibling",
            inactive_person,
            inactive_sibling,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1950,
        )
        RelationshipType.objects.filter(code="social_sibling").update(
            is_active=False,
        )
        self.assertEqual(
            get_sibling_overview(person=inactive_person)[0].person,
            inactive_sibling,
        )

    def test_person_lifecycle_rules(self) -> None:
        _, biological_input, biological_sibling = (
            self.create_biological_pair(prefix="Archivovaný biologický")
        )
        Person.objects.filter(pk=biological_sibling.pk).update(
            archived_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=biological_input)[0].person,
            biological_sibling,
        )

        explicit_input = self.create_person("Archivovaný explicitní A")
        explicit_sibling = self.create_person("Archivovaný explicitní B")
        self.create_relationship("sibling", explicit_input, explicit_sibling)
        Person.objects.filter(pk=explicit_sibling.pk).update(
            archived_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=explicit_input)[0].person,
            explicit_sibling,
        )

        _, deleted_input, deleted_biological_sibling = (
            self.create_biological_pair(prefix="Odstraněný biologický")
        )
        Person.objects.filter(pk=deleted_biological_sibling.pk).update(
            deleted_at=timezone.now(),
        )
        self.assertEqual(get_sibling_overview(person=deleted_input), ())

        deleted_explicit_input = self.create_person("Odstraněný explicitní A")
        deleted_explicit_sibling = self.create_person(
            "Odstraněný explicitní B"
        )
        self.create_relationship(
            "sibling",
            deleted_explicit_input,
            deleted_explicit_sibling,
        )
        Person.objects.filter(pk=deleted_explicit_sibling.pk).update(
            deleted_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=deleted_explicit_input),
            (),
        )

        archived_input = self.create_person("Archivovaný vstup")
        archived_input_sibling = self.create_person("Sourozenec archivu")
        self.create_relationship(
            "sibling",
            archived_input,
            archived_input_sibling,
        )
        Person.objects.filter(pk=archived_input.pk).update(
            archived_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=archived_input)[0].person,
            archived_input_sibling,
        )

        soft_deleted_input = self.create_person("Měkce odstraněný vstup")
        soft_deleted_input_sibling = self.create_person(
            "Sourozenec odstraněného"
        )
        self.create_relationship(
            "sibling",
            soft_deleted_input,
            soft_deleted_input_sibling,
        )
        Person.objects.filter(pk=soft_deleted_input.pk).update(
            deleted_at=timezone.now(),
        )
        self.assertEqual(
            get_sibling_overview(person=soft_deleted_input)[0].person,
            soft_deleted_input_sibling,
        )

    def test_unsaved_and_physically_missing_input_use_existing_error(self) -> None:
        unsaved = Person(first_name="Neuložená")
        missing = self.create_person("Fyzicky odstraněná")
        Person.objects.filter(pk=missing.pk).delete()

        for person in (unsaved, missing):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    get_sibling_overview(person=person)

                error = context.exception.error_dict["person"][0]
                self.assertEqual(error.code, "person_unsaved")

    def test_result_order_uses_names_and_pk_fallback(self) -> None:
        person = self.create_person("Vstup", last_name="Střed")
        last = self.create_person("Cyril", last_name="Zima")
        same_name_first = self.create_person("Adam", last_name="Adam")
        same_name_second = self.create_person("Adam", last_name="Adam")
        middle = self.create_person("Boris", last_name="Adam")
        for sibling in (last, same_name_second, middle, same_name_first):
            self.create_relationship("sibling", person, sibling)

        self.assertEqual(
            tuple(
                item.person
                for item in get_sibling_overview(person=person)
            ),
            (same_name_first, same_name_second, middle, last),
        )

    def test_access_levels_are_not_filtered(self) -> None:
        person = self.create_person(
            "Chráněný vstup",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        sibling = self.create_person(
            "Chráněný sourozenec",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "sibling",
            person,
            sibling,
            access_level=AccessLevel.ADMIN_ONLY,
        )

        self.assertEqual(
            get_sibling_overview(person=person)[0].person,
            sibling,
        )

    def test_selector_performs_no_writes_or_instance_changes(self) -> None:
        _, person, sibling = self.create_biological_pair(prefix="Bez zápisu")
        person_state = person.__dict__.copy()
        sibling_state = sibling.__dict__.copy()
        person_count = Person.objects.count()
        relationship_count = Relationship.objects.count()
        explicit_sibling_count = Relationship.objects.filter(
            relationship_type__code="sibling",
        ).count()

        get_sibling_overview(person=person)

        self.assertEqual(Person.objects.count(), person_count)
        self.assertEqual(Relationship.objects.count(), relationship_count)
        self.assertEqual(
            Relationship.objects.filter(
                relationship_type__code="sibling",
            ).count(),
            explicit_sibling_count,
        )
        self.assertEqual(person.__dict__, person_state)
        self.assertEqual(sibling.__dict__, sibling_state)

    def test_query_count_is_constant_without_n_plus_one(self) -> None:
        _, person, sibling = self.create_biological_pair(prefix="Dotazy")
        for index in range(5):
            explicit_sibling = self.create_person(f"Explicitní {index}")
            self.create_relationship(
                "social_sibling",
                person,
                explicit_sibling,
            )
        self.create_relationship("sibling", person, sibling)

        with self.assertNumQueries(3):
            result = get_sibling_overview(person=person)

        self.assertEqual(len(result), 6)
