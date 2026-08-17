from dataclasses import FrozenInstanceError, fields, is_dataclass
from inspect import Parameter, signature

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision, Gender

from . import selectors
from .models import Person, Relationship, RelationshipType
from .selectors import (
    RelationshipOverviewItem,
    RelationshipOverviewReason,
    get_relationship_overview,
)


class RelationshipOverviewApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu celkového přehledu vztahů."""

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

    def test_public_items_are_frozen_slotted_dataclasses(self) -> None:
        reason = RelationshipOverviewReason(
            category="sibling",
            relationship_code="biological",
            label="Biologický sourozenec",
            relationship_ids=(),
            is_derived=True,
        )
        item = RelationshipOverviewItem(
            person=Person(first_name="Test"),
            reasons=(reason,),
        )

        self.assertTrue(is_dataclass(RelationshipOverviewReason))
        self.assertTrue(is_dataclass(RelationshipOverviewItem))
        self.assertEqual(
            tuple(field.name for field in fields(RelationshipOverviewReason)),
            (
                "category",
                "relationship_code",
                "label",
                "relationship_ids",
                "is_derived",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(RelationshipOverviewItem)),
            ("person", "reasons"),
        )
        self.assertFalse(hasattr(reason, "__dict__"))
        self.assertFalse(hasattr(item, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            reason.label = "Jiný"
        with self.assertRaises(FrozenInstanceError):
            item.reasons = ()

    def test_function_uses_keyword_only_person(self) -> None:
        parameters = signature(get_relationship_overview).parameters

        self.assertEqual(tuple(parameters), ("person",))
        self.assertIs(parameters["person"].kind, Parameter.KEYWORD_ONLY)


class RelationshipOverviewSelectorTests(TestCase):
    """Ověření agregace, labelů, provenance a lifecycle."""

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
        gender: str = Gender.UNKNOWN,
        access_level: str = AccessLevel.PUBLIC,
    ) -> Person:
        return Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            gender=gender,
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

    def reasons_for(
        self,
        person: Person,
        other_person: Person,
    ) -> tuple[RelationshipOverviewReason, ...]:
        return next(
            item.reasons
            for item in get_relationship_overview(person=person)
            if item.person.pk == other_person.pk
        )

    def test_returns_tuple_with_typed_items_and_reasons(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        self.create_relationship("biological_parent", person, other)

        result = get_relationship_overview(person=person)

        self.assertIsInstance(result, tuple)
        self.assertTrue(
            all(isinstance(item, RelationshipOverviewItem) for item in result)
        )
        self.assertTrue(
            all(
                isinstance(reason, RelationshipOverviewReason)
                for item in result
                for reason in item.reasons
            )
        )

    def test_parent_types_use_forward_and_reverse_gender_labels(self) -> None:
        expected = {
            "biological_parent": ("dcera", "otec"),
            "adoptive_parent": ("adoptovaná dcera", "adoptivní otec"),
            "step_parent": ("nevlastní dcera", "nevlastní otec"),
            "foster_parent": ("pěstounská dcera", "pěstoun"),
        }
        for index, (code, labels) in enumerate(expected.items()):
            with self.subTest(code=code):
                parent = self.create_person(
                    f"Rodič {index}",
                    gender=Gender.MALE,
                )
                child = self.create_person(
                    f"Dítě {index}",
                    gender=Gender.FEMALE,
                )
                relationship = self.create_relationship(code, parent, child)

                forward = self.reasons_for(parent, child)[0]
                reverse = self.reasons_for(child, parent)[0]
                self.assertEqual(forward.label, labels[0])
                self.assertEqual(reverse.label, labels[1])
                self.assertEqual(forward.relationship_ids, (relationship.pk,))
                self.assertEqual(reverse.relationship_ids, (relationship.pk,))

    def test_parent_labels_cover_male_female_unknown_and_invalid_gender(
        self,
    ) -> None:
        parent = self.create_person("Rodič")
        expected = (
            (Gender.MALE, "syn"),
            (Gender.FEMALE, "dcera"),
            (Gender.UNKNOWN, "dítě"),
            ("legacy", "dítě"),
        )
        for index, (gender, label) in enumerate(expected):
            child = self.create_person(f"Dítě {index}", gender=Gender.UNKNOWN)
            if gender == "legacy":
                Person.objects.filter(pk=child.pk).update(gender=gender)
                child.refresh_from_db()
            else:
                child.gender = gender
                child.save(update_fields=("gender",))
            self.create_relationship("biological_parent", parent, child)

            self.assertEqual(self.reasons_for(parent, child)[0].label, label)

    def test_spouse_and_partner_labels_work_from_both_sides(self) -> None:
        for index, code in enumerate(("spouse", "partner")):
            with self.subTest(code=code):
                man = self.create_person(f"Muž {index}", gender=Gender.MALE)
                woman = self.create_person(
                    f"Žena {index}",
                    gender=Gender.FEMALE,
                )
                self.create_relationship(code, man, woman)

                self.assertEqual(
                    self.reasons_for(man, woman)[0].label,
                    "manželka" if code == "spouse" else "partnerka",
                )
                self.assertEqual(
                    self.reasons_for(woman, man)[0].label,
                    "manžel" if code == "spouse" else "partner",
                )

    def test_all_sibling_reasons_merge_with_labels_and_provenance(self) -> None:
        parent = self.create_person("Společný rodič")
        person = self.create_person("Vstup")
        sibling = self.create_person("Sestra", gender=Gender.FEMALE)
        self.create_relationship("biological_parent", parent, person)
        self.create_relationship("biological_parent", parent, sibling)
        explicit = {
            code: self.create_relationship(code, person, sibling)
            for code in (
                "sibling",
                "adoptive_sibling",
                "step_sibling",
                "social_sibling",
            )
        }

        reasons = self.reasons_for(person, sibling)

        self.assertEqual(
            tuple(reason.relationship_code for reason in reasons),
            (
                "biological",
                "sibling",
                "adoptive_sibling",
                "step_sibling",
                "social_sibling",
            ),
        )
        self.assertEqual(reasons[0].label, "Biologická sestra")
        self.assertEqual(reasons[0].relationship_ids, ())
        self.assertTrue(reasons[0].is_derived)
        for reason in reasons[1:]:
            self.assertEqual(
                reason.relationship_ids,
                (explicit[reason.relationship_code].pk,),
            )
            self.assertFalse(reason.is_derived)

    def test_biological_labels_cover_all_genders(self) -> None:
        expected = (
            (Gender.MALE, "Biologický bratr"),
            (Gender.FEMALE, "Biologická sestra"),
            (Gender.UNKNOWN, "Biologický sourozenec"),
        )
        for index, (gender, label) in enumerate(expected):
            parent = self.create_person(f"Rodič {index}")
            person = self.create_person(f"Vstup {index}")
            sibling = self.create_person(f"Sourozenec {index}", gender=gender)
            self.create_relationship("biological_parent", parent, person)
            self.create_relationship("biological_parent", parent, sibling)

            self.assertEqual(self.reasons_for(person, sibling)[0].label, label)

    def test_godparent_guardian_social_and_other_labels(self) -> None:
        person = self.create_person("Vstup", gender=Gender.MALE)
        cases = (
            ("godparent", Gender.FEMALE, "kmotřenka", "kmotr"),
            ("guardian", Gender.FEMALE, "svěřenkyně", "poručník"),
            (
                "family_friend",
                Gender.FEMALE,
                "rodinná přítelkyně",
                "rodinný přítel",
            ),
            ("other", Gender.UNKNOWN, "související osoba", "související osoba"),
        )
        for index, (code, gender, forward, reverse) in enumerate(cases):
            with self.subTest(code=code):
                other = self.create_person(f"Druhá {index}", gender=gender)
                self.create_relationship(code, person, other)
                self.assertEqual(self.reasons_for(person, other)[0].label, forward)
                self.assertEqual(self.reasons_for(other, person)[0].label, reverse)

    def test_custom_relationship_type_is_included_and_ordered(self) -> None:
        custom_type = RelationshipType.objects.create(
            code="mentor",
            name="Mentorství",
            category="care",
            sort_order=5,
            forward_label_male="svěřenec",
            forward_label_female="svěřenkyně",
            forward_label_unknown="svěřená osoba",
            reverse_label_male="mentor",
            reverse_label_female="mentorka",
            reverse_label_unknown="mentor nebo mentorka",
        )
        self.relationship_types[custom_type.code] = custom_type
        person = self.create_person("Mentor")
        other = self.create_person("Svěřenkyně", gender=Gender.FEMALE)
        relationship = self.create_relationship("mentor", person, other)

        reason = self.reasons_for(person, other)[0]

        self.assertEqual(reason.category, "care")
        self.assertEqual(reason.relationship_code, "mentor")
        self.assertEqual(reason.label, "svěřenkyně")
        self.assertEqual(reason.relationship_ids, (relationship.pk,))

    def test_multiple_categories_merge_once_in_category_order(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá", gender=Gender.FEMALE)
        for code in ("other", "family_friend", "godparent", "partner"):
            self.create_relationship(code, person, other)

        result = get_relationship_overview(person=person)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            tuple(reason.category for reason in result[0].reasons),
            ("partner", "godparent", "social", "other"),
        )

    def test_multiple_periods_merge_ids_in_ascending_order(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Partnerka", gender=Gender.FEMALE)
        relationships = [
            self.create_relationship(
                "partner",
                person,
                other,
                date_precision=DatePrecision.EXACT,
                start_year=year,
                start_month=1,
                start_day=1,
            )
            for year in (2000, 1990)
        ]

        reasons = self.reasons_for(person, other)

        self.assertEqual(len(reasons), 1)
        self.assertEqual(
            reasons[0].relationship_ids,
            tuple(sorted(relationship.pk for relationship in relationships)),
        )

    def test_same_code_with_different_directional_labels_stays_distinct(
        self,
    ) -> None:
        relationship_type = RelationshipType.objects.create(
            code="teacher",
            name="Učitelská vazba",
            category="social",
            sort_order=15,
            forward_label_male="žák",
            forward_label_female="žákyně",
            forward_label_unknown="žák nebo žákyně",
            reverse_label_male="učitel",
            reverse_label_female="učitelka",
            reverse_label_unknown="učitel nebo učitelka",
        )
        self.relationship_types[relationship_type.code] = relationship_type
        person = self.create_person("Vstup", gender=Gender.MALE)
        other = self.create_person("Druhá", gender=Gender.FEMALE)
        forward = self.create_relationship("teacher", person, other)
        reverse = self.create_relationship("teacher", other, person)

        reasons = self.reasons_for(person, other)

        self.assertEqual(len(reasons), 2)
        self.assertEqual(
            tuple(reason.label for reason in reasons),
            ("učitelka", "žákyně"),
        )
        self.assertEqual(
            {reason.relationship_ids for reason in reasons},
            {(forward.pk,), (reverse.pk,)},
        )

    def test_reason_order_uses_category_derived_sort_order_code_and_label(
        self,
    ) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        parent = self.create_person("Rodič")
        self.create_relationship("biological_parent", parent, person)
        self.create_relationship("biological_parent", parent, other)
        for code in (
            "other",
            "social_sibling",
            "sibling",
            "partner",
            "biological_parent",
        ):
            if code == "biological_parent":
                self.create_relationship(code, person, other)
            else:
                self.create_relationship(code, person, other)

        self.assertEqual(
            tuple(
                reason.relationship_code
                for reason in self.reasons_for(person, other)
            ),
            (
                "biological_parent",
                "partner",
                "biological",
                "sibling",
                "social_sibling",
                "other",
            ),
        )

    def test_result_people_are_ordered_by_names_and_pk(self) -> None:
        person = self.create_person("Vstup", last_name="Střed")
        last = self.create_person("Cyril", last_name="Zima")
        first = self.create_person("Adam", last_name="Adam")
        same = self.create_person("Adam", last_name="Adam")
        middle = self.create_person("Boris", last_name="Adam")
        for other in (last, same, middle, first):
            self.create_relationship("biological_parent", person, other)

        self.assertEqual(
            tuple(
                item.person
                for item in get_relationship_overview(person=person)
            ),
            (first, same, middle, last),
        )

    def test_relationship_and_person_lifecycle_rules(self) -> None:
        person = self.create_person("Vstup")
        archived_person = self.create_person("Archivovaná")
        deleted_person = self.create_person("Odstraněná")
        archived_relationship = self.create_relationship(
            "biological_parent",
            person,
            archived_person,
        )
        deleted_relationship = self.create_relationship(
            "adoptive_parent",
            person,
            archived_person,
        )
        self.create_relationship("biological_parent", person, deleted_person)
        now = timezone.now()
        Relationship.objects.filter(pk=archived_relationship.pk).update(
            archived_at=now,
        )
        Relationship.objects.filter(pk=deleted_relationship.pk).update(
            deleted_at=now,
        )
        Person.objects.filter(pk=archived_person.pk).update(archived_at=now)
        Person.objects.filter(pk=deleted_person.pk).update(deleted_at=now)
        RelationshipType.objects.filter(code="biological_parent").update(
            is_active=False,
        )

        result = get_relationship_overview(person=person)

        self.assertEqual(
            tuple(item.person.pk for item in result),
            (archived_person.pk,),
        )
        self.assertEqual(
            result[0].reasons[0].relationship_ids,
            (archived_relationship.pk,),
        )

    def test_historical_relationship_is_included(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Historická")
        relationship = self.create_relationship(
            "partner",
            person,
            other,
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1910,
        )

        self.assertEqual(
            self.reasons_for(person, other)[0].relationship_ids,
            (relationship.pk,),
        )

    def test_archived_and_soft_deleted_inputs_are_supported(self) -> None:
        for field_name in ("archived_at", "deleted_at"):
            person = self.create_person(f"Vstup {field_name}")
            other = self.create_person(f"Druhá {field_name}")
            self.create_relationship("biological_parent", person, other)
            Person.objects.filter(pk=person.pk).update(
                **{field_name: timezone.now()}
            )

            self.assertEqual(
                get_relationship_overview(person=person)[0].person,
                other,
            )

    def test_unsaved_and_physically_missing_inputs_keep_stable_error(self) -> None:
        unsaved = Person(first_name="Neuložená")
        missing = self.create_person("Fyzicky odstraněná")
        Person.objects.filter(pk=missing.pk).delete()

        for person in (unsaved, missing):
            with self.subTest(person=person.first_name):
                with self.assertRaises(ValidationError) as context:
                    get_relationship_overview(person=person)

                error = context.exception.error_dict["person"][0]
                self.assertEqual(error.code, "person_unsaved")

    def test_permissionless_result_includes_all_access_levels(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person(
            "Chráněná",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        public = self.create_relationship(
            "partner",
            person,
            other,
            access_level=AccessLevel.PUBLIC,
            date_precision=DatePrecision.EXACT,
            start_year=2000,
            start_month=1,
            start_day=1,
        )
        restricted = self.create_relationship(
            "partner",
            person,
            other,
            access_level=AccessLevel.RESTRICTED,
            date_precision=DatePrecision.EXACT,
            start_year=2010,
            start_month=1,
            start_day=1,
        )

        self.assertEqual(
            self.reasons_for(person, other)[0].relationship_ids,
            (public.pk, restricted.pk),
        )

    def test_selector_performs_no_writes_or_instance_changes(self) -> None:
        person = self.create_person("Vstup")
        other = self.create_person("Druhá")
        self.create_relationship("biological_parent", person, other)
        person_state = person.__dict__.copy()
        other_state = other.__dict__.copy()
        person_count = Person.objects.count()
        relationship_count = Relationship.objects.count()

        get_relationship_overview(person=person)

        self.assertEqual(Person.objects.count(), person_count)
        self.assertEqual(Relationship.objects.count(), relationship_count)
        self.assertEqual(person.__dict__, person_state)
        self.assertEqual(other.__dict__, other_state)

    def test_query_count_is_constant_without_n_plus_one(self) -> None:
        person = self.create_person("Vstup")
        first = self.create_person("První")
        self.create_relationship("biological_parent", person, first)

        with self.assertNumQueries(5):
            get_relationship_overview(person=person)

        for index in range(5):
            other = self.create_person(f"Další {index}")
            self.create_relationship("biological_parent", person, other)
            self.create_relationship("godparent", person, other)

        with self.assertNumQueries(5):
            result = get_relationship_overview(person=person)

        self.assertEqual(len(result), 6)
