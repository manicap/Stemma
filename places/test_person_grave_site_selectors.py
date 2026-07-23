from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from people.models import Person

from . import selectors
from .choices import GraveSiteStatus
from .models import (
    GraveSite,
    GraveSiteType,
    PersonGraveSite,
    PersonGraveSiteRole,
    Place,
)
from .selectors import (
    get_grave_site_person_links,
    get_person_grave_site_links,
)


class PersonGraveSiteSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu permissionless selectorů vazeb."""

    def test_module_exports_exact_approved_api(self) -> None:
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
            selectors.get_person_grave_site_links,
            get_person_grave_site_links,
        )
        self.assertIs(
            selectors.get_grave_site_person_links,
            get_grave_site_person_links,
        )

    def test_person_selector_has_exact_keyword_only_parameter(self) -> None:
        parameters = signature(get_person_grave_site_links).parameters

        self.assertEqual(tuple(parameters), ("person",))
        self.assertIs(
            parameters["person"].kind,
            Parameter.KEYWORD_ONLY,
        )

    def test_grave_site_selector_has_exact_keyword_only_parameter(
        self,
    ) -> None:
        parameters = signature(get_grave_site_person_links).parameters

        self.assertEqual(tuple(parameters), ("grave_site",))
        self.assertIs(
            parameters["grave_site"].kind,
            Parameter.KEYWORD_ONLY,
        )


class PersonGraveSiteSelectorTests(TestCase):
    """Ověření úplných interních přehledů vazeb osob a hrobových míst."""

    person_error_message = (
        "Osoba musí být uložená a existovat v databázi."
    )
    grave_site_error_message = (
        "Hrobové nebo pamětní místo musí být uložené a existovat "
        "v databázi."
    )

    def setUp(self) -> None:
        self.person = self.create_person("Anna")
        self.other_person = self.create_person("Berta")
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.grave_site = self.create_grave_site(
            cemetery_name="Hřbitov A",
        )
        self.other_grave_site = self.create_grave_site(
            cemetery_name="Hřbitov B",
        )
        self.role = PersonGraveSiteRole.objects.get(code="buried")

    @staticmethod
    def create_person(
        first_name: str,
        **overrides: object,
    ) -> Person:
        values = {
            "first_name": first_name,
            "last_name": "Testovací",
        }
        values.update(overrides)
        return Person.objects.create(**values)

    @staticmethod
    def create_role(
        code: str,
        *,
        name: str | None = None,
        sort_order: int = 100,
        is_active: bool = True,
        is_system: bool = False,
    ) -> PersonGraveSiteRole:
        return PersonGraveSiteRole.objects.create(
            code=code,
            name=name or code,
            sort_order=sort_order,
            is_active=is_active,
            is_system=is_system,
        )

    @staticmethod
    def create_type(
        code: str,
        *,
        is_active: bool = True,
        is_system: bool = False,
    ) -> GraveSiteType:
        return GraveSiteType.objects.create(
            code=code,
            name=code,
            is_active=is_active,
            is_system=is_system,
        )

    def create_grave_site(self, **overrides: object) -> GraveSite:
        values = {
            "grave_site_type": self.grave_site_type,
            "location_text": "Základní lokalita",
        }
        values.update(overrides)
        return GraveSite.objects.create(**values)

    def create_link(self, **overrides: object) -> PersonGraveSite:
        values = {
            "person": self.person,
            "grave_site": self.grave_site,
            "role": self.role,
        }
        values.update(overrides)
        return PersonGraveSite.objects.create(**values)

    def assert_selector_error(
        self,
        *,
        key: str,
        code: str,
        message: str,
        callback,
    ) -> None:
        with self.assertRaises(ValidationError) as context:
            callback()

        self.assertEqual(tuple(context.exception.error_dict), (key,))
        error = context.exception.error_dict[key][0]
        self.assertEqual(error.code, code)
        self.assertEqual(error.message, message)

    def test_both_selectors_return_lazy_person_grave_site_querysets(
        self,
    ) -> None:
        for callback in (
            lambda: get_person_grave_site_links(person=self.person),
            lambda: get_grave_site_person_links(
                grave_site=self.grave_site
            ),
        ):
            with self.subTest(selector=callback):
                with self.assertNumQueries(1):
                    queryset = callback()

                self.assertIsInstance(queryset, QuerySet)
                self.assertIs(queryset.model, PersonGraveSite)
                with self.assertNumQueries(1):
                    self.assertEqual(list(queryset), [])

    def test_person_without_primary_key_is_rejected_without_query(
        self,
    ) -> None:
        person = Person(first_name="Neuložená")

        with self.assertNumQueries(0):
            self.assert_selector_error(
                key="person",
                code="person_unsaved",
                message=self.person_error_message,
                callback=lambda: get_person_grave_site_links(person=person),
            )

    def test_physically_missing_person_is_rejected(self) -> None:
        person = self.create_person("Odstraněná")
        person_id = person.pk
        person.delete()
        person.pk = person_id

        with self.assertNumQueries(1):
            self.assert_selector_error(
                key="person",
                code="person_unsaved",
                message=self.person_error_message,
                callback=lambda: get_person_grave_site_links(person=person),
            )

    def test_grave_site_without_primary_key_is_rejected_without_query(
        self,
    ) -> None:
        grave_site = GraveSite()

        with self.assertNumQueries(0):
            self.assert_selector_error(
                key="grave_site",
                code="grave_site_unsaved",
                message=self.grave_site_error_message,
                callback=lambda: get_grave_site_person_links(
                    grave_site=grave_site
                ),
            )

    def test_physically_missing_grave_site_is_rejected(self) -> None:
        grave_site = self.create_grave_site(location_text="Odstraněné")
        grave_site_id = grave_site.pk
        grave_site.delete()
        grave_site.pk = grave_site_id

        with self.assertNumQueries(1):
            self.assert_selector_error(
                key="grave_site",
                code="grave_site_unsaved",
                message=self.grave_site_error_message,
                callback=lambda: get_grave_site_person_links(
                    grave_site=grave_site
                ),
            )

    def test_person_selector_returns_all_requested_person_links_only(
        self,
    ) -> None:
        second_role = self.create_role("person_overview_second")
        expected = [
            self.create_link(),
            self.create_link(),
            self.create_link(role=second_role),
            self.create_link(grave_site=self.other_grave_site),
        ]
        self.create_link(person=self.other_person)

        result = list(get_person_grave_site_links(person=self.person))

        self.assertEqual(set(result), set(expected))
        self.assertEqual(len(result), 4)

    def test_grave_site_selector_returns_all_requested_site_links_only(
        self,
    ) -> None:
        second_role = self.create_role("site_overview_second")
        expected = [
            self.create_link(),
            self.create_link(),
            self.create_link(role=second_role),
            self.create_link(person=self.other_person),
        ]
        self.create_link(grave_site=self.other_grave_site)

        result = list(
            get_grave_site_person_links(grave_site=self.grave_site)
        )

        self.assertEqual(set(result), set(expected))
        self.assertEqual(len(result), 4)

    def test_both_selectors_include_archived_and_exclude_deleted_links(
        self,
    ) -> None:
        regular = self.create_link()
        archived = self.create_link()
        deleted = self.create_link()
        now = timezone.now()
        PersonGraveSite.objects.filter(pk=archived.pk).update(
            archived_at=now
        )
        PersonGraveSite.objects.filter(pk=deleted.pk).update(
            deleted_at=now
        )

        self.assertEqual(
            list(get_person_grave_site_links(person=self.person)),
            [regular, archived],
        )
        self.assertEqual(
            list(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            [regular, archived],
        )

    def test_person_selector_accepts_all_existing_input_lifecycles(
        self,
    ) -> None:
        now = timezone.now()
        regular = self.create_person("Běžná")
        archived = self.create_person("Archivovaná")
        deleted = self.create_person("Odstraněná")
        Person.objects.filter(pk=archived.pk).update(archived_at=now)
        Person.objects.filter(pk=deleted.pk).update(deleted_at=now)
        expected = {
            regular.pk: self.create_link(person=regular),
            archived.pk: self.create_link(person=archived),
            deleted.pk: self.create_link(person=deleted),
        }

        for person in (regular, archived, deleted):
            with self.subTest(person=person.first_name):
                self.assertEqual(
                    list(get_person_grave_site_links(person=person)),
                    [expected[person.pk]],
                )

    def test_grave_site_selector_accepts_all_lifecycles_and_statuses(
        self,
    ) -> None:
        now = timezone.now()
        cases = (
            ("regular", GraveSiteStatus.EXISTING, None, None),
            ("archived", GraveSiteStatus.DESTROYED, now, None),
            ("deleted", GraveSiteStatus.UNKNOWN, None, now),
        )

        for label, status, archived_at, deleted_at in cases:
            grave_site = self.create_grave_site(
                location_text=label,
                status=status,
                archived_at=archived_at,
                deleted_at=deleted_at,
            )
            link = self.create_link(grave_site=grave_site)
            with self.subTest(label=label):
                self.assertEqual(
                    list(
                        get_grave_site_person_links(
                            grave_site=grave_site
                        )
                    ),
                    [link],
                )

    def test_selectors_ignore_stale_input_lifecycle_and_status_fields(
        self,
    ) -> None:
        link = self.create_link()
        now = timezone.now()
        self.person.archived_at = now
        self.person.deleted_at = now
        self.grave_site.archived_at = now
        self.grave_site.deleted_at = now
        self.grave_site.status = GraveSiteStatus.DESTROYED

        self.assertEqual(
            list(get_person_grave_site_links(person=self.person)),
            [link],
        )
        self.assertEqual(
            list(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            [link],
        )

    def test_person_selector_includes_all_grave_site_lifecycles(
        self,
    ) -> None:
        now = timezone.now()
        regular = self.create_grave_site(location_text="Běžné")
        archived = self.create_grave_site(
            location_text="Archivované",
            archived_at=now,
        )
        deleted = self.create_grave_site(
            location_text="Odstraněné",
            deleted_at=now,
        )
        expected = {
            self.create_link(grave_site=regular),
            self.create_link(grave_site=archived),
            self.create_link(grave_site=deleted),
        }

        self.assertEqual(
            set(get_person_grave_site_links(person=self.person)),
            expected,
        )

    def test_grave_site_selector_includes_all_person_lifecycles(
        self,
    ) -> None:
        now = timezone.now()
        regular = self.create_person("Běžná")
        archived = self.create_person("Archivovaná", archived_at=now)
        deleted = self.create_person("Odstraněná", deleted_at=now)
        expected = {
            self.create_link(person=regular),
            self.create_link(person=archived),
            self.create_link(person=deleted),
        }

        self.assertEqual(
            set(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            expected,
        )

    def test_both_selectors_include_all_access_levels(self) -> None:
        expected = {
            self.create_link(access_level=access_level)
            for access_level in AccessLevel.values
        }

        self.assertEqual(
            set(get_person_grave_site_links(person=self.person)),
            expected,
        )
        self.assertEqual(
            set(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            expected,
        )

    def test_both_selectors_include_all_verification_statuses(self) -> None:
        expected = {
            self.create_link(verification_status=status)
            for status in VerificationStatus.values
        }

        self.assertEqual(
            set(get_person_grave_site_links(person=self.person)),
            expected,
        )
        self.assertEqual(
            set(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            expected,
        )

    def test_both_selectors_include_system_user_and_inactive_roles(
        self,
    ) -> None:
        active_user_role = self.create_role("active_user_role")
        inactive_role = self.create_role(
            "inactive_system_role",
            is_active=False,
            is_system=True,
        )
        expected = {
            self.create_link(role=self.role),
            self.create_link(role=active_user_role),
            self.create_link(role=inactive_role),
        }

        self.assertEqual(
            set(get_person_grave_site_links(person=self.person)),
            expected,
        )
        self.assertEqual(
            set(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            expected,
        )

    def test_person_selector_ignores_grave_site_status_and_type_state(
        self,
    ) -> None:
        inactive_type = self.create_type(
            "selector_inactive_type",
            is_active=False,
        )
        user_type = self.create_type("selector_user_type")
        sites = [
            self.create_grave_site(
                location_text=status,
                status=status,
            )
            for status in GraveSiteStatus.values
        ]
        sites.extend(
            (
                self.create_grave_site(
                    grave_site_type=inactive_type,
                    location_text="Neaktivní typ",
                ),
                self.create_grave_site(
                    grave_site_type=user_type,
                    location_text="Uživatelský typ",
                ),
            )
        )
        expected = {
            self.create_link(grave_site=grave_site)
            for grave_site in sites
        }

        self.assertEqual(
            set(get_person_grave_site_links(person=self.person)),
            expected,
        )

    def test_person_selector_uses_exact_approved_ordering(self) -> None:
        role_a = self.create_role(
            "person_order_a",
            name="A",
            sort_order=10,
        )
        role_b = self.create_role(
            "person_order_b",
            name="B",
            sort_order=10,
        )
        cemetery_b = self.create_grave_site(
            location_text="",
            cemetery_name="B",
        )
        section_b = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="B",
        )
        row_b = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="B",
        )
        number_two = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="2",
        )
        same_location_first = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
        )
        same_location_second = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
        )
        cemetery_b_link = self.create_link(grave_site=cemetery_b)
        section_b_link = self.create_link(grave_site=section_b)
        row_b_link = self.create_link(grave_site=row_b)
        number_two_link = self.create_link(grave_site=number_two)
        first_site_link = self.create_link(
            grave_site=same_location_first,
            role=role_b,
        )
        second_site_role_b = self.create_link(
            grave_site=same_location_second,
            role=role_b,
        )
        second_site_role_a_first = self.create_link(
            grave_site=same_location_second,
            role=role_a,
        )
        second_site_role_a_second = self.create_link(
            grave_site=same_location_second,
            role=role_a,
        )

        self.assertEqual(
            list(get_person_grave_site_links(person=self.person)),
            [
                first_site_link,
                second_site_role_a_first,
                second_site_role_a_second,
                second_site_role_b,
                number_two_link,
                row_b_link,
                section_b_link,
                cemetery_b_link,
            ],
        )

    def test_grave_site_selector_uses_exact_approved_ordering(
        self,
    ) -> None:
        role_a = self.create_role(
            "site_order_a",
            name="A",
            sort_order=10,
        )
        role_b = self.create_role(
            "site_order_b",
            name="B",
            sort_order=10,
        )
        later_person = self.create_person("Pozdější")
        later_person_link = self.create_link(
            person=later_person,
            role=role_a,
        )
        role_b_link = self.create_link(role=role_b)
        role_a_first = self.create_link(role=role_a)
        role_a_second = self.create_link(role=role_a)

        self.assertEqual(
            list(
                get_grave_site_person_links(grave_site=self.grave_site)
            ),
            [
                role_a_first,
                role_a_second,
                role_b_link,
                later_person_link,
            ],
        )

    def assert_related_access_uses_one_query(
        self,
        queryset: QuerySet[PersonGraveSite],
        expected_count: int,
    ) -> None:
        with self.assertNumQueries(1):
            result = list(queryset)
            for link in result:
                str(link.person)
                str(link.grave_site)
                str(link.grave_site.grave_site_type)
                str(link.grave_site.place)
                str(link.role)
                str(link.created_by)

        self.assertEqual(len(result), expected_count)

    def test_person_selector_query_profile_is_constant_without_n_plus_one(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="person-link-selector"
        )
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            place=self.place
        )
        self.create_link(created_by=creator)
        with self.assertNumQueries(1):
            one_queryset = get_person_grave_site_links(person=self.person)
        self.assert_related_access_uses_one_query(one_queryset, 1)

        for _ in range(7):
            self.create_link(created_by=creator)
        with self.assertNumQueries(1):
            many_queryset = get_person_grave_site_links(person=self.person)
        self.assert_related_access_uses_one_query(many_queryset, 8)

    def test_grave_site_selector_query_profile_is_constant_without_n_plus_one(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="site-link-selector"
        )
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            place=self.place
        )
        self.create_link(created_by=creator)
        with self.assertNumQueries(1):
            one_queryset = get_grave_site_person_links(
                grave_site=self.grave_site
            )
        self.assert_related_access_uses_one_query(one_queryset, 1)

        for index in range(7):
            person = self.create_person(f"Osoba {index}")
            self.create_link(person=person, created_by=creator)
        with self.assertNumQueries(1):
            many_queryset = get_grave_site_person_links(
                grave_site=self.grave_site
            )
        self.assert_related_access_uses_one_query(many_queryset, 8)

    def test_both_selectors_are_permissionless_and_return_private_links(
        self,
    ) -> None:
        restricted = self.create_link(
            access_level=AccessLevel.RESTRICTED
        )
        admin_only = self.create_link(
            access_level=AccessLevel.ADMIN_ONLY
        )

        self.assertNotIn(
            "actor",
            signature(get_person_grave_site_links).parameters,
        )
        self.assertNotIn(
            "actor",
            signature(get_grave_site_person_links).parameters,
        )
        with patch(
            "places.selectors.can_view_access_level"
        ) as permission_policy:
            person_result = list(
                get_person_grave_site_links(person=self.person)
            )
            site_result = list(
                get_grave_site_person_links(grave_site=self.grave_site)
            )

        permission_policy.assert_not_called()
        self.assertEqual(person_result, [restricted, admin_only])
        self.assertEqual(site_result, [restricted, admin_only])

    def test_selector_returns_historically_unusual_combination(self) -> None:
        inactive_role = self.create_role(
            "historical_role",
            is_active=False,
        )
        memorial_type = GraveSiteType.objects.get(code="memorial")
        grave_site = self.create_grave_site(
            grave_site_type=memorial_type,
            status=GraveSiteStatus.DESTROYED,
            location_text="Historické místo",
        )
        link = self.create_link(
            grave_site=grave_site,
            role=inactive_role,
        )

        with patch.object(
            PersonGraveSite,
            "full_clean",
            side_effect=AssertionError("Selector nesmí validovat model."),
        ):
            self.assertEqual(
                list(get_person_grave_site_links(person=self.person)),
                [link],
            )
            self.assertEqual(
                list(
                    get_grave_site_person_links(grave_site=grave_site)
                ),
                [link],
            )

    def test_selectors_perform_no_writes_or_instance_changes(self) -> None:
        creator = get_user_model().objects.create_user(
            username="link-selector-immutable"
        )
        link = self.create_link(
            created_by=creator,
            note="Původní poznámka",
        )
        person_state = self.person.__dict__.copy()
        grave_site_state = self.grave_site.__dict__.copy()
        link_values = PersonGraveSite.objects.values_list(
            "person_id",
            "grave_site_id",
            "role_id",
            "note",
            "updated_at",
        ).get(pk=link.pk)
        role_values = PersonGraveSiteRole.objects.values_list(
            "name",
            "is_active",
        ).get(pk=self.role.pk)
        creator_values = get_user_model().objects.values_list(
            "username",
            "is_active",
        ).get(pk=creator.pk)

        list(get_person_grave_site_links(person=self.person))
        list(get_grave_site_person_links(grave_site=self.grave_site))

        self.assertEqual(self.person.__dict__, person_state)
        self.assertEqual(self.grave_site.__dict__, grave_site_state)
        self.assertEqual(
            PersonGraveSite.objects.values_list(
                "person_id",
                "grave_site_id",
                "role_id",
                "note",
                "updated_at",
            ).get(pk=link.pk),
            link_values,
        )
        self.assertEqual(
            PersonGraveSiteRole.objects.values_list(
                "name",
                "is_active",
            ).get(pk=self.role.pk),
            role_values,
        )
        self.assertEqual(
            get_user_model().objects.values_list(
                "username",
                "is_active",
            ).get(pk=creator.pk),
            creator_values,
        )

    def test_no_prefetch_or_aggregation_and_unrelated_links_do_not_matter(
        self,
    ) -> None:
        expected = self.create_link()
        for index in range(6):
            person = self.create_person(f"Jiná {index}")
            grave_site = self.create_grave_site(
                location_text=f"Jiné místo {index}"
            )
            self.create_link(person=person, grave_site=grave_site)

        with self.assertNumQueries(1):
            person_queryset = get_person_grave_site_links(
                person=self.person
            )
        with self.assertNumQueries(1):
            site_queryset = get_grave_site_person_links(
                grave_site=self.grave_site
            )
        self.assertEqual(person_queryset._prefetch_related_lookups, ())
        self.assertEqual(site_queryset._prefetch_related_lookups, ())

        with self.assertNumQueries(1):
            person_result = list(person_queryset)
        with self.assertNumQueries(1):
            site_result = list(site_queryset)

        self.assertEqual(person_result, [expected])
        self.assertEqual(site_result, [expected])
