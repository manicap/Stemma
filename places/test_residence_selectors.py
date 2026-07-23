from datetime import date
from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import (
    AccessLevel,
    DatePrecision,
    VerificationStatus,
)
from people.models import Person

from . import selectors
from .models import Place, Residence, ResidenceType
from .selectors import get_person_residences, get_visible_person_residences


class ResidenceSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu selectoru bydlišť."""

    def test_module_exports_only_approved_public_api(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "get_grave_site_person_links",
                "get_grave_sites",
                "get_person_grave_site_links",
                "get_person_residences",
                "get_visible_person_residences",
            ),
        )
        self.assertIs(
            selectors.get_person_residences,
            get_person_residences,
        )
        self.assertIs(
            selectors.get_visible_person_residences,
            get_visible_person_residences,
        )

    def test_person_is_the_only_keyword_only_parameter(self) -> None:
        parameters = signature(get_person_residences).parameters

        self.assertEqual(tuple(parameters), ("person",))
        self.assertIs(
            parameters["person"].kind,
            Parameter.KEYWORD_ONLY,
        )


class ResidenceSelectorTests(TestCase):
    """Ověření permissionless přehledu bydlišť jedné osoby."""

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="První",
        )
        self.other_person = Person.objects.create(
            first_name="Bohumil",
            last_name="Druhý",
        )
        self.residence_type = self.make_type(
            "selector_primary",
            name="Hlavní",
            sort_order=10,
            is_system=True,
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )

    @staticmethod
    def make_type(
        code: str,
        *,
        name: str | None = None,
        sort_order: int = 0,
        is_active: bool = True,
        is_system: bool = False,
    ) -> ResidenceType:
        return ResidenceType.objects.create(
            code=code,
            name=name or code,
            sort_order=sort_order,
            is_active=is_active,
            is_system=is_system,
        )

    def create_residence(self, **overrides: object) -> Residence:
        values = {
            "person": self.person,
            "residence_type": self.residence_type,
            "place": self.place,
        }
        values.update(overrides)
        residence = Residence(**values)
        residence.full_clean()
        residence.save()
        return residence

    def assert_person_unsaved(self, person: Person) -> None:
        with self.assertRaises(ValidationError) as context:
            get_person_residences(person=person)

        self.assertIn("person", context.exception.error_dict)
        error = context.exception.error_dict["person"][0]
        self.assertEqual(error.code, "person_unsaved")
        self.assertEqual(
            error.message,
            "Osoba musí být uložená a existovat v databázi.",
        )

    def test_returns_lazy_residence_queryset(self) -> None:
        residence = self.create_residence()

        with self.assertNumQueries(1):
            result = get_person_residences(person=self.person)

        self.assertIsInstance(result, QuerySet)
        self.assertIs(result.model, Residence)
        with self.assertNumQueries(1):
            self.assertEqual(list(result), [residence])

    def test_rejects_person_without_primary_key(self) -> None:
        self.assert_person_unsaved(Person(first_name="Neuložená"))

    def test_rejects_physically_missing_person(self) -> None:
        missing = Person.objects.create(first_name="Odstraněná")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        self.assert_person_unsaved(missing)

    def test_returns_only_requested_person_residences(self) -> None:
        expected = [
            self.create_residence(address_text=f"Adresa {index}")
            for index in range(3)
        ]
        self.create_residence(
            person=self.other_person,
            address_text="Jiná osoba",
        )

        result = list(get_person_residences(person=self.person))

        self.assertEqual(result, expected)
        self.assertTrue(
            all(residence.person_id == self.person.pk for residence in result)
        )

    def test_includes_regular_and_archived_but_not_deleted_residence(
        self,
    ) -> None:
        regular = self.create_residence(address_text="Běžné")
        archived = self.create_residence(address_text="Archivované")
        deleted = self.create_residence(address_text="Odstraněné")
        now = timezone.now()
        Residence.objects.filter(pk=archived.pk).update(archived_at=now)
        Residence.objects.filter(pk=deleted.pk).update(deleted_at=now)

        result = list(get_person_residences(person=self.person))

        self.assertEqual(result, [regular, archived])

    def test_accepts_archived_input_person(self) -> None:
        residence = self.create_residence()
        Person.objects.filter(pk=self.person.pk).update(
            archived_at=timezone.now()
        )

        self.assertEqual(
            list(get_person_residences(person=self.person)),
            [residence],
        )

    def test_accepts_soft_deleted_input_person(self) -> None:
        residence = self.create_residence()
        Person.objects.filter(pk=self.person.pk).update(
            deleted_at=timezone.now()
        )

        self.assertEqual(
            list(get_person_residences(person=self.person)),
            [residence],
        )

    def test_does_not_filter_access_levels(self) -> None:
        expected = [
            self.create_residence(
                address_text=access_level,
                access_level=access_level,
            )
            for access_level in AccessLevel.values
        ]

        self.assertEqual(
            list(get_person_residences(person=self.person)),
            expected,
        )

    def test_does_not_filter_verification_statuses(self) -> None:
        expected = [
            self.create_residence(
                address_text=verification_status,
                verification_status=verification_status,
            )
            for verification_status in VerificationStatus.values
        ]

        self.assertEqual(
            list(get_person_residences(person=self.person)),
            expected,
        )

    def test_includes_system_user_and_inactive_residence_types(self) -> None:
        user_type = self.make_type(
            "selector_user",
            name="Uživatelský",
        )
        inactive_type = self.make_type(
            "selector_inactive",
            name="Neaktivní",
            is_active=False,
        )
        expected = [
            self.create_residence(address_text="Systémový"),
            self.create_residence(
                residence_type=user_type,
                address_text="Uživatelský",
            ),
            self.create_residence(
                residence_type=inactive_type,
                address_text="Neaktivní",
            ),
        ]

        self.assertEqual(
            set(get_person_residences(person=self.person)),
            set(expected),
        )

    def test_includes_all_supported_location_variants(self) -> None:
        only_place = self.create_residence(address_text="")
        only_text = self.create_residence(
            place=None,
            address_text="Historická lokalita",
        )
        both = self.create_residence(address_text="Ulice 12")

        self.assertEqual(
            list(get_person_residences(person=self.person)),
            [only_place, only_text, both],
        )

    def test_includes_unknown_partial_and_historical_or_future_ranges(
        self,
    ) -> None:
        unknown = self.create_residence(address_text="Neznámé")
        year = self.create_residence(
            address_text="Rok",
            date_precision=DatePrecision.YEAR,
            start_year=1950,
        )
        historical = self.create_residence(
            address_text="Historické",
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1910,
        )
        future = self.create_residence(
            address_text="Budoucí",
            date_precision=DatePrecision.RANGE,
            start_year=2100,
            end_year=2110,
        )

        result = set(get_person_residences(person=self.person))

        self.assertEqual(result, {unknown, year, historical, future})

    def test_ordering_uses_dates_type_order_name_and_primary_key(
        self,
    ) -> None:
        alpha_type = self.make_type(
            "selector_alpha",
            name="Alfa",
            sort_order=10,
        )
        beta_type = self.make_type(
            "selector_beta",
            name="Beta",
            sort_order=10,
        )
        late_type = self.make_type(
            "selector_late",
            name="Pozdní typ",
            sort_order=99,
        )
        unknown = self.create_residence(address_text="Neznámé")
        exact = self.create_residence(
            residence_type=late_type,
            address_text="Přesné",
            date_precision=DatePrecision.EXACT,
            start_year=1900,
            start_month=1,
            start_day=1,
        )
        alpha_first = self.create_residence(
            residence_type=alpha_type,
            address_text="Alfa první",
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1900,
        )
        alpha_second = self.create_residence(
            residence_type=alpha_type,
            address_text="Alfa druhé",
            date_precision=DatePrecision.RANGE,
            start_year=1900,
            end_year=1900,
        )
        beta = self.create_residence(
            residence_type=beta_type,
            address_text="Beta",
            date_precision=DatePrecision.YEAR,
            start_year=1900,
        )

        result = list(get_person_residences(person=self.person))

        self.assertEqual(
            result,
            [unknown, exact, alpha_first, alpha_second, beta],
        )
        self.assertIsNone(unknown.sort_date)
        self.assertEqual(exact.sort_date, date(1900, 1, 1))
        self.assertEqual(exact.sort_date_end, date(1900, 1, 1))
        self.assertEqual(alpha_first.sort_date_end, date(1900, 12, 31))

    def test_select_related_keeps_query_count_constant_for_one_result(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="selector-one"
        )
        self.create_residence(created_by=creator)
        queryset = get_person_residences(person=self.person)

        with self.assertNumQueries(1):
            result = list(queryset)
            for residence in result:
                str(residence.person)
                str(residence.residence_type)
                str(residence.place)
                str(residence.created_by)

    def test_select_related_keeps_query_count_constant_for_many_results(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="selector-many"
        )
        for index in range(8):
            self.create_residence(
                address_text=f"Adresa {index}",
                created_by=creator,
            )
        queryset = get_person_residences(person=self.person)

        with self.assertNumQueries(1):
            result = list(queryset)
            for residence in result:
                str(residence.person)
                str(residence.residence_type)
                str(residence.place)
                str(residence.created_by)

        self.assertEqual(len(result), 8)

    def test_selector_performs_no_writes_or_instance_changes(self) -> None:
        residence = self.create_residence(address_text="Beze změny")
        person_state = self.person.__dict__.copy()
        residence_values = Residence.objects.values_list(
            "person_id",
            "residence_type_id",
            "place_id",
            "address_text",
            "updated_at",
        ).get(pk=residence.pk)
        type_values = ResidenceType.objects.values_list(
            "name",
            "is_active",
        ).get(pk=self.residence_type.pk)
        place_values = Place.objects.values_list(
            "name",
            "normalized_name",
        ).get(pk=self.place.pk)

        list(get_person_residences(person=self.person))

        self.assertEqual(self.person.__dict__, person_state)
        self.assertEqual(
            Residence.objects.values_list(
                "person_id",
                "residence_type_id",
                "place_id",
                "address_text",
                "updated_at",
            ).get(pk=residence.pk),
            residence_values,
        )
        self.assertEqual(
            ResidenceType.objects.values_list(
                "name",
                "is_active",
            ).get(pk=self.residence_type.pk),
            type_values,
        )
        self.assertEqual(
            Place.objects.values_list(
                "name",
                "normalized_name",
            ).get(pk=self.place.pk),
            place_values,
        )

    def test_permissionless_selector_has_no_actor_and_returns_private_data(
        self,
    ) -> None:
        restricted = self.create_residence(
            access_level=AccessLevel.RESTRICTED,
            address_text="Omezené",
        )
        admin_only = self.create_residence(
            access_level=AccessLevel.ADMIN_ONLY,
            address_text="Správce",
        )
        Residence.objects.filter(pk=admin_only.pk).update(
            archived_at=timezone.now()
        )

        self.assertNotIn("actor", signature(get_person_residences).parameters)
        self.assertEqual(
            list(get_person_residences(person=self.person)),
            [restricted, admin_only],
        )

    def test_selector_does_not_revalidate_historical_location(self) -> None:
        residence = self.create_residence(address_text="Původní")
        Residence.objects.filter(pk=residence.pk).update(
            place=None,
            address_text="",
        )

        result = list(get_person_residences(person=self.person))

        self.assertEqual([item.pk for item in result], [residence.pk])
        self.assertIsNone(result[0].place_id)
        self.assertEqual(result[0].address_text, "")
