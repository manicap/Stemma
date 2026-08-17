from inspect import Parameter, signature

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision

from . import selectors
from .models import Person, Relationship, RelationshipType
from .selectors import get_biological_siblings


class RelationshipSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu selectoru vazeb."""

    def test_module_exports_only_approved_public_api(self) -> None:
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
        self.assertIs(
            selectors.get_biological_siblings,
            get_biological_siblings,
        )

    def test_person_is_keyword_only(self) -> None:
        parameters = signature(get_biological_siblings).parameters

        self.assertEqual(tuple(parameters), ("person",))
        self.assertIs(
            parameters["person"].kind,
            Parameter.KEYWORD_ONLY,
        )


class BiologicalSiblingSelectorTests(TestCase):
    """Ověření čtecího odvozování biologických sourozenců."""

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

    def create_biological_siblings(
        self,
        *,
        prefix: str,
        relationship_values: dict[str, object] | None = None,
    ) -> tuple[Person, Person, Person]:
        parent = self.create_person(f"{prefix} rodič")
        person = self.create_person(f"{prefix} osoba")
        sibling = self.create_person(f"{prefix} sourozenec")
        values = relationship_values or {}
        self.create_relationship(
            "biological_parent",
            parent,
            person,
            **values,
        )
        self.create_relationship(
            "biological_parent",
            parent,
            sibling,
            **values,
        )
        return parent, person, sibling

    def assert_sibling_ids(
        self,
        person: Person,
        expected: list[Person],
    ) -> None:
        self.assertEqual(
            set(get_biological_siblings(person=person).values_list(
                "pk",
                flat=True,
            )),
            {expected_person.pk for expected_person in expected},
        )

    def test_returns_lazy_person_queryset_with_constant_queries(self) -> None:
        _, person, sibling = self.create_biological_siblings(prefix="Lazy")

        with self.assertNumQueries(1):
            result = get_biological_siblings(person=person)

        self.assertIsInstance(result, QuerySet)
        self.assertIs(result.model, Person)
        with self.assertNumQueries(1):
            self.assertEqual(list(result), [sibling])

    def test_one_shared_parent_is_symmetric(self) -> None:
        _, person, sibling = self.create_biological_siblings(prefix="Jeden")

        self.assert_sibling_ids(person, [sibling])
        self.assert_sibling_ids(sibling, [person])

    def test_two_shared_parents_return_each_sibling_once(self) -> None:
        person = self.create_person("Dítě A")
        sibling = self.create_person("Dítě B")
        for index in range(2):
            parent = self.create_person(f"Společný rodič {index}")
            self.create_relationship(
                "biological_parent",
                parent,
                person,
            )
            self.create_relationship(
                "biological_parent",
                parent,
                sibling,
            )

        self.assertEqual(
            list(get_biological_siblings(person=person)),
            [sibling],
        )
        self.assertEqual(
            list(get_biological_siblings(person=sibling)),
            [person],
        )

    def test_half_siblings_are_included(self) -> None:
        person = self.create_person("Poloviční A")
        sibling = self.create_person("Poloviční B")
        shared_parent = self.create_person("Společný rodič")
        self.create_relationship(
            "biological_parent",
            shared_parent,
            person,
        )
        self.create_relationship(
            "biological_parent",
            shared_parent,
            sibling,
        )
        self.create_relationship(
            "biological_parent",
            self.create_person("Rodič pouze A"),
            person,
        )
        self.create_relationship(
            "biological_parent",
            self.create_person("Rodič pouze B"),
            sibling,
        )

        self.assert_sibling_ids(person, [sibling])
        self.assert_sibling_ids(sibling, [person])

    def test_multiple_siblings_exclude_input_and_keep_person_ordering(self) -> None:
        parent = self.create_person("Řadicí rodič")
        person = self.create_person("Vstup", last_name="Novák")
        sibling_c = self.create_person("Cyril", last_name="Zima")
        sibling_a = self.create_person("Adam", last_name="Adam")
        sibling_b = self.create_person("Boris", last_name="Adam")
        for child in (person, sibling_c, sibling_a, sibling_b):
            self.create_relationship(
                "biological_parent",
                parent,
                child,
            )

        result = list(get_biological_siblings(person=person))

        self.assertEqual(result, [sibling_a, sibling_b, sibling_c])
        self.assertNotIn(person, result)

    def test_non_biological_parent_types_do_not_create_siblings(self) -> None:
        for index, code in enumerate(
            (
                "adoptive_parent",
                "step_parent",
                "foster_parent",
                "guardian",
            )
        ):
            with self.subTest(code=code):
                parent = self.create_person(f"Jiný rodič {index}")
                person = self.create_person(f"Jiné dítě A {index}")
                sibling = self.create_person(f"Jiné dítě B {index}")
                self.create_relationship(code, parent, person)
                self.create_relationship(code, parent, sibling)

                self.assert_sibling_ids(person, [])

    def test_explicit_sibling_types_are_ignored_without_duplication(self) -> None:
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
                self.assert_sibling_ids(person, [])

        _, person, sibling = self.create_biological_siblings(prefix="Smíšený")
        self.create_relationship("sibling", person, sibling)

        self.assertEqual(
            list(get_biological_siblings(person=person)),
            [sibling],
        )

    def test_relationship_lifecycle_rules(self) -> None:
        _, archived_person, archived_sibling = (
            self.create_biological_siblings(prefix="Archivovaná vazba")
        )
        Relationship.objects.filter(
            person_b__in=(archived_person, archived_sibling),
        ).update(archived_at=timezone.now())
        self.assert_sibling_ids(archived_person, [archived_sibling])

        _, deleted_person, deleted_sibling = (
            self.create_biological_siblings(prefix="Odstraněná vazba")
        )
        Relationship.objects.filter(person_b=deleted_sibling).update(
            deleted_at=timezone.now(),
        )
        self.assert_sibling_ids(deleted_person, [])

        _, inactive_person, inactive_sibling = (
            self.create_biological_siblings(prefix="Neaktivní typ")
        )
        RelationshipType.objects.filter(code="biological_parent").update(
            is_active=False,
        )
        self.assert_sibling_ids(inactive_person, [inactive_sibling])

    def test_all_date_precisions_are_ignored_by_derivation(self) -> None:
        date_values = (
            ("unknown", {}),
            (
                "exact",
                {
                    "date_precision": DatePrecision.EXACT,
                    "start_year": 2000,
                    "start_month": 1,
                    "start_day": 2,
                },
            ),
            (
                "month",
                {
                    "date_precision": DatePrecision.MONTH,
                    "start_year": 2000,
                    "start_month": 2,
                },
            ),
            (
                "year",
                {
                    "date_precision": DatePrecision.YEAR,
                    "start_year": 2000,
                },
            ),
            (
                "historical_range",
                {
                    "date_precision": DatePrecision.RANGE,
                    "start_year": 1900,
                    "end_year": 1950,
                },
            ),
        )
        for label, values in date_values:
            with self.subTest(precision=label):
                _, person, sibling = self.create_biological_siblings(
                    prefix=label,
                    relationship_values=values,
                )
                self.assert_sibling_ids(person, [sibling])

    def test_historical_range_is_isolated_in_test_data(self) -> None:
        biological_parent = self.relationship_types["biological_parent"]
        self.assertFalse(biological_parent.supports_date_range)
        _, person, sibling = self.create_biological_siblings(
            prefix="Starší RANGE",
            relationship_values={
                "date_precision": DatePrecision.RANGE,
                "start_year": 1800,
                "end_year": 1850,
            },
        )

        self.assert_sibling_ids(person, [sibling])
        biological_parent.refresh_from_db()
        self.assertFalse(biological_parent.supports_date_range)

    def test_person_lifecycle_rules(self) -> None:
        _, archived_person, archived_sibling = (
            self.create_biological_siblings(prefix="Archivovaná osoba")
        )
        Person.objects.filter(pk=archived_sibling.pk).update(
            archived_at=timezone.now(),
        )
        self.assert_sibling_ids(archived_person, [archived_sibling])

        _, deleted_person, deleted_sibling = (
            self.create_biological_siblings(prefix="Odstraněná osoba")
        )
        Person.objects.filter(pk=deleted_sibling.pk).update(
            deleted_at=timezone.now(),
        )
        self.assert_sibling_ids(deleted_person, [])

        _, archived_input, archived_input_sibling = (
            self.create_biological_siblings(prefix="Archivovaný vstup")
        )
        Person.objects.filter(pk=archived_input.pk).update(
            archived_at=timezone.now(),
        )
        self.assert_sibling_ids(archived_input, [archived_input_sibling])

        _, deleted_input, deleted_input_sibling = (
            self.create_biological_siblings(prefix="Odstraněný vstup")
        )
        Person.objects.filter(pk=deleted_input.pk).update(
            deleted_at=timezone.now(),
        )
        self.assert_sibling_ids(deleted_input, [deleted_input_sibling])

    def test_access_levels_are_not_filtered(self) -> None:
        parent = self.create_person("Chráněný rodič")
        person = self.create_person(
            "Chráněný vstup",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        sibling = self.create_person(
            "Chráněný sourozenec",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_relationship(
            "biological_parent",
            parent,
            person,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        self.create_relationship(
            "biological_parent",
            parent,
            sibling,
            access_level=AccessLevel.RESTRICTED,
        )

        self.assert_sibling_ids(person, [sibling])

    def test_unsaved_and_physically_missing_person_use_stable_error(self) -> None:
        unsaved_person = Person(first_name="Neuložená")
        deleted_person = self.create_person("Fyzicky odstraněná")
        Person.objects.filter(pk=deleted_person.pk).delete()

        for person in (unsaved_person, deleted_person):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    get_biological_siblings(person=person)

                error = context.exception.error_dict["person"][0]
                self.assertEqual(error.code, "person_unsaved")
                self.assertEqual(
                    error.message,
                    "Osoba musí být před vyhledáním sourozenců uložena.",
                )

    def test_selector_performs_no_writes_or_instance_changes(self) -> None:
        _, person, sibling = self.create_biological_siblings(prefix="Čtení")
        person_state = person.__dict__.copy()
        person_count = Person.objects.count()
        relationship_count = Relationship.objects.count()
        explicit_sibling_count = Relationship.objects.filter(
            relationship_type__code="sibling",
        ).count()

        self.assertEqual(
            list(get_biological_siblings(person=person)),
            [sibling],
        )

        self.assertEqual(Person.objects.count(), person_count)
        self.assertEqual(Relationship.objects.count(), relationship_count)
        self.assertEqual(
            Relationship.objects.filter(
                relationship_type__code="sibling",
            ).count(),
            explicit_sibling_count,
        )
        self.assertEqual(person.__dict__, person_state)
