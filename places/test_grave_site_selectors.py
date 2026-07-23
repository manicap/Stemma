from decimal import Decimal
from inspect import signature

from django.contrib.auth import get_user_model
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
from .selectors import get_grave_sites


class GraveSiteSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu permissionless selectoru."""

    def test_module_exports_exact_approved_api(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "get_grave_site_person_links",
                "get_grave_sites",
                "get_person_grave_site_links",
                "get_person_residences",
                "get_visible_grave_site_person_links",
                "get_visible_grave_sites",
                "get_visible_person_grave_site_links",
                "get_visible_person_residences",
            ),
        )
        self.assertIs(selectors.get_grave_sites, get_grave_sites)

    def test_selector_has_no_parameters_and_returns_grave_site_queryset(
        self,
    ) -> None:
        self.assertEqual(tuple(signature(get_grave_sites).parameters), ())
        result = get_grave_sites()

        self.assertIsInstance(result, QuerySet)
        self.assertIs(result.model, GraveSite)


class GraveSiteSelectorTests(TestCase):
    """Ověření úplného interního katalogu nesmazaných hrobových míst."""

    def setUp(self) -> None:
        self.system_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )

    @staticmethod
    def make_type(
        code: str,
        *,
        is_active: bool = True,
    ) -> GraveSiteType:
        return GraveSiteType.objects.create(
            code=code,
            name=code,
            is_active=is_active,
        )

    def create_grave_site(self, **overrides: object) -> GraveSite:
        values = {
            "grave_site_type": self.system_type,
            "location_text": "Základní lokalita",
        }
        values.update(overrides)
        grave_site = GraveSite(**values)
        grave_site.full_clean()
        grave_site.save()
        return grave_site

    def test_empty_database_returns_empty_lazy_queryset(self) -> None:
        with self.assertNumQueries(0):
            queryset = get_grave_sites()

        with self.assertNumQueries(1):
            result = list(queryset)

        self.assertEqual(result, [])

    def test_returns_multiple_grave_sites_only(self) -> None:
        expected = [
            self.create_grave_site(location_text=f"Místo {index}")
            for index in range(3)
        ]

        result = list(get_grave_sites())

        self.assertEqual(result, expected)
        self.assertTrue(all(isinstance(item, GraveSite) for item in result))

    def test_includes_regular_and_archived_but_not_deleted(self) -> None:
        regular = self.create_grave_site(location_text="Běžné")
        archived = self.create_grave_site(location_text="Archivované")
        deleted = self.create_grave_site(location_text="Odstraněné")
        now = timezone.now()
        GraveSite.objects.filter(pk=archived.pk).update(archived_at=now)
        GraveSite.objects.filter(pk=deleted.pk).update(deleted_at=now)

        result = list(get_grave_sites())

        self.assertEqual(result, [regular, archived])

    def test_includes_all_statuses(self) -> None:
        expected = [
            self.create_grave_site(
                location_text=status,
                status=status,
            )
            for status in GraveSiteStatus.values
        ]

        self.assertEqual(set(get_grave_sites()), set(expected))

    def test_includes_all_access_levels(self) -> None:
        expected = [
            self.create_grave_site(
                location_text=access_level,
                access_level=access_level,
            )
            for access_level in AccessLevel.values
        ]

        self.assertEqual(set(get_grave_sites()), set(expected))

    def test_includes_all_verification_statuses(self) -> None:
        expected = [
            self.create_grave_site(
                location_text=verification_status,
                verification_status=verification_status,
            )
            for verification_status in VerificationStatus.values
        ]

        self.assertEqual(set(get_grave_sites()), set(expected))

    def test_includes_system_user_and_inactive_types(self) -> None:
        user_type = self.make_type("selector_user_type")
        inactive_type = self.make_type(
            "selector_inactive_type",
            is_active=False,
        )
        expected = [
            self.create_grave_site(location_text="Systémový"),
            self.create_grave_site(
                grave_site_type=user_type,
                location_text="Uživatelský",
            ),
            self.create_grave_site(
                grave_site_type=inactive_type,
                location_text="Neaktivní",
            ),
        ]

        self.assertEqual(set(get_grave_sites()), set(expected))

    def test_includes_all_location_variants(self) -> None:
        only_place = self.create_grave_site(
            place=self.place,
            location_text="",
        )
        only_text = self.create_grave_site(location_text="Text")
        only_cemetery = self.create_grave_site(
            location_text="",
            cemetery_name="Hřbitov",
        )
        only_coordinates = self.create_grave_site(
            location_text="",
            latitude=Decimal("50.000001"),
            longitude=Decimal("14.000001"),
        )
        combined = self.create_grave_site(
            place=self.place,
            location_text="Detail",
            cemetery_name="Městský hřbitov",
            latitude=Decimal("50.100001"),
            longitude=Decimal("14.100001"),
        )

        self.assertEqual(
            set(get_grave_sites()),
            {
                only_place,
                only_text,
                only_cemetery,
                only_coordinates,
                combined,
            },
        )

    def test_selector_does_not_revalidate_historical_location(self) -> None:
        grave_site = self.create_grave_site(location_text="Původní")
        GraveSite.objects.filter(pk=grave_site.pk).update(
            place=None,
            location_text="",
            cemetery_name="",
            latitude=None,
            longitude=None,
        )

        result = list(get_grave_sites())

        self.assertEqual([item.pk for item in result], [grave_site.pk])
        self.assertEqual(result[0].location_text, "")

    def test_uses_exact_model_ordering_with_primary_key_fallback(
        self,
    ) -> None:
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
        grave_two = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="2",
        )
        same_first = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
            status=GraveSiteStatus.DESTROYED,
            access_level=AccessLevel.ADMIN_ONLY,
        )
        same_second = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
            status=GraveSiteStatus.EXISTING,
            verification_status=VerificationStatus.VERIFIED,
        )

        self.assertEqual(
            list(get_grave_sites()),
            [
                same_first,
                same_second,
                grave_two,
                row_b,
                section_b,
                cemetery_b,
            ],
        )

    def test_select_related_keeps_query_count_constant_for_one_result(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="grave-selector-one"
        )
        self.create_grave_site(place=self.place, created_by=creator)
        queryset = get_grave_sites()

        with self.assertNumQueries(1):
            result = list(queryset)
            for grave_site in result:
                str(grave_site.grave_site_type)
                str(grave_site.place)
                str(grave_site.created_by)

    def test_select_related_keeps_query_count_constant_for_many_results(
        self,
    ) -> None:
        creator = get_user_model().objects.create_user(
            username="grave-selector-many"
        )
        for index in range(8):
            self.create_grave_site(
                place=self.place,
                location_text=f"Místo {index}",
                created_by=creator,
            )
        queryset = get_grave_sites()

        with self.assertNumQueries(1):
            result = list(queryset)
            for grave_site in result:
                str(grave_site.grave_site_type)
                str(grave_site.place)
                str(grave_site.created_by)

        self.assertEqual(len(result), 8)

    def test_permissionless_selector_has_no_actor_and_returns_private_data(
        self,
    ) -> None:
        restricted = self.create_grave_site(
            location_text="Omezené",
            access_level=AccessLevel.RESTRICTED,
        )
        admin_only = self.create_grave_site(
            location_text="Správce",
            access_level=AccessLevel.ADMIN_ONLY,
            status=GraveSiteStatus.DESTROYED,
        )
        GraveSite.objects.filter(pk=admin_only.pk).update(
            archived_at=timezone.now()
        )

        self.assertNotIn("actor", signature(get_grave_sites).parameters)
        self.assertEqual(
            list(get_grave_sites()),
            [restricted, admin_only],
        )

    def test_selector_does_not_prefetch_or_materialize_person_links(
        self,
    ) -> None:
        grave_site = self.create_grave_site()
        person = Person.objects.create(first_name="Anna")
        role = PersonGraveSiteRole.objects.get(code="buried")
        for _ in range(6):
            PersonGraveSite.objects.create(
                person=person,
                grave_site=grave_site,
                role=role,
            )

        with self.assertNumQueries(0):
            queryset = get_grave_sites()
        self.assertEqual(queryset._prefetch_related_lookups, ())

        with self.assertNumQueries(1):
            result = list(queryset)

        self.assertEqual(result, [grave_site])
        self.assertEqual(PersonGraveSite.objects.count(), 6)

    def test_selector_performs_no_writes_or_instance_changes(self) -> None:
        creator = get_user_model().objects.create_user(
            username="grave-selector-immutable"
        )
        grave_site = self.create_grave_site(
            place=self.place,
            created_by=creator,
        )
        person = Person.objects.create(first_name="Anna")
        role = PersonGraveSiteRole.objects.get(code="buried")
        link = PersonGraveSite.objects.create(
            person=person,
            grave_site=grave_site,
            role=role,
        )
        site_values = GraveSite.objects.values_list(
            "grave_site_type_id",
            "place_id",
            "location_text",
            "status",
            "updated_at",
        ).get(pk=grave_site.pk)
        type_values = GraveSiteType.objects.values_list(
            "name",
            "is_active",
        ).get(pk=self.system_type.pk)
        place_values = Place.objects.values_list(
            "name",
            "normalized_name",
        ).get(pk=self.place.pk)
        creator_values = get_user_model().objects.values_list(
            "username",
            "is_active",
        ).get(pk=creator.pk)
        link_values = PersonGraveSite.objects.values_list(
            "person_id",
            "grave_site_id",
            "role_id",
            "updated_at",
        ).get(pk=link.pk)

        list(get_grave_sites())

        self.assertEqual(
            GraveSite.objects.values_list(
                "grave_site_type_id",
                "place_id",
                "location_text",
                "status",
                "updated_at",
            ).get(pk=grave_site.pk),
            site_values,
        )
        self.assertEqual(
            GraveSiteType.objects.values_list(
                "name",
                "is_active",
            ).get(pk=self.system_type.pk),
            type_values,
        )
        self.assertEqual(
            Place.objects.values_list(
                "name",
                "normalized_name",
            ).get(pk=self.place.pk),
            place_values,
        )
        self.assertEqual(
            get_user_model().objects.values_list(
                "username",
                "is_active",
            ).get(pk=creator.pk),
            creator_values,
        )
        self.assertEqual(
            PersonGraveSite.objects.values_list(
                "person_id",
                "grave_site_id",
                "role_id",
                "updated_at",
            ).get(pk=link.pk),
            link_values,
        )
