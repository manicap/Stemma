from decimal import Decimal
from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus

from . import selectors
from .choices import GraveSiteStatus
from .models import GraveSite, GraveSiteType, Place
from .selectors import get_grave_sites, get_visible_grave_sites


class VisibleGraveSiteSelectorApiTests(SimpleTestCase):
    """Ověření veřejného kontraktu autorizovaného selectoru."""

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
        self.assertIs(
            selectors.get_visible_grave_sites,
            get_visible_grave_sites,
        )

    def test_selector_has_exact_keyword_only_actor_parameter(self) -> None:
        parameters = signature(get_visible_grave_sites).parameters

        self.assertEqual(tuple(parameters), ("actor",))
        self.assertIs(
            parameters["actor"].kind,
            Parameter.KEYWORD_ONLY,
        )


class VisibleGraveSiteSelectorTests(TestCase):
    """Ověření autorizovaného katalogu hrobových a pamětních míst."""

    def setUp(self) -> None:
        self.system_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )

    @staticmethod
    def create_user(username: str, **values: object):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(
            content_type__app_label="accounts",
            content_type__model="user",
            codename=codename,
        )

    def grant(self, actor, *codenames: str) -> None:
        actor.user_permissions.add(
            *(self.permission(codename) for codename in codenames)
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
            "grave_site_type": self.system_type,
            "location_text": "Základní lokalita",
        }
        values.update(overrides)
        return GraveSite.objects.create(**values)

    def create_access_sites(self) -> dict[str, GraveSite]:
        return {
            access_level: self.create_grave_site(
                location_text=access_level,
                access_level=access_level,
            )
            for access_level in AccessLevel.values
        }

    def assert_visible_levels(
        self,
        actor,
        expected: set[str],
    ) -> None:
        self.assertEqual(
            {
                grave_site.access_level
                for grave_site in get_visible_grave_sites(actor=actor)
            },
            expected,
        )

    def assert_actor_error(self, actor, code: str, message: str) -> None:
        with self.assertRaises(ValidationError) as context:
            get_visible_grave_sites(actor=actor)

        self.assertEqual(tuple(context.exception.error_dict), ("actor",))
        error = context.exception.error_dict["actor"][0]
        self.assertEqual(error.code, code)
        self.assertEqual(error.message, message)

    def test_returns_lazy_grave_site_queryset(self) -> None:
        self.create_grave_site()

        with self.assertNumQueries(0):
            queryset = get_visible_grave_sites(actor=AnonymousUser())

        self.assertIsInstance(queryset, QuerySet)
        self.assertIs(queryset.model, GraveSite)
        with self.assertNumQueries(1):
            result = list(queryset)
        self.assertEqual(len(result), 1)

    def test_invalid_actor_uses_actor_invalid(self) -> None:
        for actor in (None, object()):
            with self.subTest(actor=actor):
                with self.assertNumQueries(0):
                    self.assert_actor_error(
                        actor,
                        "actor_invalid",
                        "Actor není platným uživatelem ani anonymním "
                        "návštěvníkem.",
                    )

    def test_unsaved_and_physically_missing_actor_use_actor_unsaved(
        self,
    ) -> None:
        unsaved = get_user_model()(username="unsaved-grave-selector")
        missing = self.create_user("missing-grave-selector")
        get_user_model().objects.filter(pk=missing.pk).delete()

        for actor in (unsaved, missing):
            with self.subTest(actor=actor.username):
                self.assert_actor_error(
                    actor,
                    "actor_unsaved",
                    "Přihlášený uživatel musí být uložený a existovat "
                    "v databázi.",
                )

    def test_each_access_level_is_evaluated_once(self) -> None:
        with patch(
            "places.selectors.can_view_access_level",
            wraps=selectors.can_view_access_level,
        ) as permission_check:
            get_visible_grave_sites(actor=AnonymousUser())

        self.assertEqual(permission_check.call_count, 4)
        self.assertEqual(
            {
                call.kwargs["access_level"]
                for call in permission_check.call_args_list
            },
            set(AccessLevel.values),
        )

    def test_anonymous_user_sees_only_public(self) -> None:
        self.create_access_sites()

        self.assert_visible_levels(
            AnonymousUser(),
            {AccessLevel.PUBLIC},
        )

    def test_active_ordinary_user_sees_public_and_authenticated(
        self,
    ) -> None:
        self.create_access_sites()
        actor = self.create_user("ordinary-grave-selector")

        self.assert_visible_levels(
            actor,
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
            },
        )

    def test_restricted_permission_does_not_grant_admin_only(self) -> None:
        self.create_access_sites()
        actor = self.create_user("restricted-grave-selector")
        self.grant(actor, "view_restricted_content")

        self.assert_visible_levels(
            actor,
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.RESTRICTED,
            },
        )

    def test_admin_only_permission_does_not_grant_restricted(self) -> None:
        self.create_access_sites()
        actor = self.create_user("admin-grave-selector")
        self.grant(actor, "view_admin_only_content")

        self.assert_visible_levels(
            actor,
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
                AccessLevel.ADMIN_ONLY,
            },
        )

    def test_both_permissions_and_superuser_see_all_levels(self) -> None:
        self.create_access_sites()
        both = self.create_user("both-grave-selector")
        self.grant(
            both,
            "view_restricted_content",
            "view_admin_only_content",
        )
        superuser = self.create_user(
            "superuser-grave-selector",
            is_superuser=True,
        )

        for actor in (both, superuser):
            with self.subTest(actor=actor.username):
                self.assert_visible_levels(
                    actor,
                    set(AccessLevel.values),
                )

    def test_is_staff_does_not_extend_access(self) -> None:
        self.create_access_sites()
        actor = self.create_user(
            "staff-grave-selector",
            is_staff=True,
        )

        self.assert_visible_levels(
            actor,
            {
                AccessLevel.PUBLIC,
                AccessLevel.AUTHENTICATED,
            },
        )

    def test_inactive_privileged_user_is_treated_as_anonymous(
        self,
    ) -> None:
        self.create_access_sites()
        actor = self.create_user(
            "inactive-manager-grave-selector",
            is_active=False,
            is_staff=True,
            is_superuser=True,
        )
        self.grant(
            actor,
            "view_restricted_content",
            "view_admin_only_content",
        )
        actor.groups.add(Group.objects.get(name="Správce"))

        self.assert_visible_levels(
            actor,
            {AccessLevel.PUBLIC},
        )

    def test_uses_fresh_actor_permissions_groups_and_flags(self) -> None:
        self.create_access_sites()
        actor = self.create_user("stale-grave-selector")
        current_actor = get_user_model().objects.get(pk=actor.pk)

        self.grant(current_actor, "view_restricted_content")
        self.assertIn(
            AccessLevel.RESTRICTED,
            {
                site.access_level
                for site in get_visible_grave_sites(actor=actor)
            },
        )
        current_actor.user_permissions.clear()
        current_actor.groups.add(Group.objects.get(name="Správce"))
        self.assert_visible_levels(actor, set(AccessLevel.values))

        current_actor.groups.clear()
        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=True
        )
        self.assert_visible_levels(actor, set(AccessLevel.values))

        get_user_model().objects.filter(pk=actor.pk).update(
            is_active=False,
            is_superuser=False,
            is_staff=True,
        )
        self.assert_visible_levels(actor, {AccessLevel.PUBLIC})

    def test_lifecycle_includes_archived_and_excludes_deleted(self) -> None:
        regular = self.create_grave_site(location_text="Běžné")
        archived = self.create_grave_site(location_text="Archivované")
        deleted = self.create_grave_site(location_text="Odstraněné")
        now = timezone.now()
        GraveSite.objects.filter(pk=archived.pk).update(archived_at=now)
        GraveSite.objects.filter(pk=deleted.pk).update(deleted_at=now)
        superuser = self.create_user(
            "lifecycle-superuser",
            is_superuser=True,
        )

        for actor in (AnonymousUser(), superuser):
            with self.subTest(
                actor=getattr(actor, "username", "anonymous")
            ):
                self.assertEqual(
                    list(get_visible_grave_sites(actor=actor)),
                    [regular, archived],
                )

    def test_status_does_not_affect_visible_results(self) -> None:
        expected = {
            self.create_grave_site(
                location_text=status,
                status=status,
            )
            for status in GraveSiteStatus.values
        }

        self.assertEqual(
            set(get_visible_grave_sites(actor=AnonymousUser())),
            expected,
        )

    def test_type_activity_and_system_state_do_not_affect_results(
        self,
    ) -> None:
        inactive_type = self.create_type(
            "visible_inactive_type",
            is_active=False,
        )
        user_type = self.create_type("visible_user_type")
        expected = {
            self.create_grave_site(location_text="Systémový"),
            self.create_grave_site(
                grave_site_type=inactive_type,
                location_text="Neaktivní",
            ),
            self.create_grave_site(
                grave_site_type=user_type,
                location_text="Uživatelský",
            ),
        }

        self.assertEqual(
            set(get_visible_grave_sites(actor=AnonymousUser())),
            expected,
        )

    def test_verification_status_does_not_affect_visible_results(
        self,
    ) -> None:
        expected = {
            self.create_grave_site(
                location_text=status,
                verification_status=status,
            )
            for status in VerificationStatus.values
        }

        self.assertEqual(
            set(get_visible_grave_sites(actor=AnonymousUser())),
            expected,
        )

    def test_all_location_variants_remain_visible(self) -> None:
        expected = {
            self.create_grave_site(place=self.place, location_text=""),
            self.create_grave_site(location_text="Text"),
            self.create_grave_site(
                location_text="",
                cemetery_name="Hřbitov",
            ),
            self.create_grave_site(
                location_text="",
                latitude=Decimal("50.000001"),
                longitude=Decimal("14.000001"),
            ),
            self.create_grave_site(
                place=self.place,
                location_text="Detail",
                cemetery_name="Městský hřbitov",
                latitude=Decimal("50.100001"),
                longitude=Decimal("14.100001"),
            ),
        }

        self.assertEqual(
            set(get_visible_grave_sites(actor=AnonymousUser())),
            expected,
        )

    def test_place_access_and_lifecycle_are_not_authorized_separately(
        self,
    ) -> None:
        Place.objects.filter(pk=self.place.pk).update(
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        grave_site = self.create_grave_site(
            place=self.place,
            access_level=AccessLevel.PUBLIC,
        )

        self.assertEqual(
            list(get_visible_grave_sites(actor=AnonymousUser())),
            [grave_site],
        )

    def test_historically_invalid_visible_row_is_not_revalidated(
        self,
    ) -> None:
        grave_site = self.create_grave_site(location_text="Původní")
        GraveSite.objects.filter(pk=grave_site.pk).update(
            place=None,
            location_text="",
            cemetery_name="",
            latitude=None,
            longitude=None,
        )

        with patch.object(
            GraveSite,
            "full_clean",
            side_effect=AssertionError("Selector nesmí validovat model."),
        ):
            result = list(
                get_visible_grave_sites(actor=AnonymousUser())
            )

        self.assertEqual([item.pk for item in result], [grave_site.pk])

    def test_permissionless_selector_contract_remains_unchanged(
        self,
    ) -> None:
        sites = self.create_access_sites()

        permissionless_queryset = get_grave_sites()
        visible_queryset = get_visible_grave_sites(actor=AnonymousUser())

        self.assertIsInstance(permissionless_queryset, QuerySet)
        self.assertIsInstance(visible_queryset, QuerySet)
        self.assertEqual(set(permissionless_queryset), set(sites.values()))
        self.assertEqual(
            list(visible_queryset),
            [sites[AccessLevel.PUBLIC]],
        )

    def test_access_filter_preserves_exact_model_ordering(self) -> None:
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
        same_first = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
            access_level=AccessLevel.PUBLIC,
        )
        self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        same_second = self.create_grave_site(
            location_text="",
            cemetery_name="A",
            section="A",
            row="A",
            grave_number="1",
            access_level=AccessLevel.PUBLIC,
            status=GraveSiteStatus.DESTROYED,
            verification_status=VerificationStatus.VERIFIED,
        )

        self.assertEqual(
            list(get_visible_grave_sites(actor=AnonymousUser())),
            [
                same_first,
                same_second,
                number_two,
                row_b,
                section_b,
                cemetery_b,
            ],
        )

    def assert_related_access_uses_one_query(
        self,
        queryset: QuerySet[GraveSite],
        expected_count: int,
    ) -> None:
        with self.assertNumQueries(1):
            result = list(queryset)
            for grave_site in result:
                str(grave_site.grave_site_type)
                str(grave_site.place)
                str(grave_site.created_by)

        self.assertEqual(len(result), expected_count)

    def test_select_related_query_profile_is_constant(self) -> None:
        creator = self.create_user("visible-grave-creator")
        self.create_grave_site(
            place=self.place,
            created_by=creator,
        )
        with self.assertNumQueries(0):
            one_queryset = get_visible_grave_sites(
                actor=AnonymousUser()
            )
        self.assert_related_access_uses_one_query(one_queryset, 1)

        for index in range(1, 8):
            self.create_grave_site(
                place=self.place,
                location_text=f"Místo {index}",
                created_by=creator,
            )
        with self.assertNumQueries(0):
            many_queryset = get_visible_grave_sites(
                actor=AnonymousUser()
            )
        self.assert_related_access_uses_one_query(many_queryset, 8)

    def test_actor_and_result_query_counts_are_dataset_independent(
        self,
    ) -> None:
        actor = self.create_user("visible-grave-query-profile")
        self.create_grave_site()

        with CaptureQueriesContext(connection) as small_actor_queries:
            small_queryset = get_visible_grave_sites(actor=actor)
        with CaptureQueriesContext(connection) as small_result_queries:
            list(small_queryset)

        for index in range(7):
            self.create_grave_site(location_text=f"Další {index}")

        with CaptureQueriesContext(connection) as large_actor_queries:
            large_queryset = get_visible_grave_sites(actor=actor)
        with CaptureQueriesContext(connection) as large_result_queries:
            list(large_queryset)

        self.assertEqual(
            len(small_actor_queries),
            len(large_actor_queries),
        )
        self.assertEqual(len(small_result_queries), 1)
        self.assertEqual(len(large_result_queries), 1)

    def test_selector_performs_no_writes(self) -> None:
        actor = self.create_user("visible-grave-immutable")
        self.grant(actor, "view_restricted_content")
        grave_site = self.create_grave_site(
            place=self.place,
            created_by=actor,
            access_level=AccessLevel.RESTRICTED,
        )
        site_values = GraveSite.objects.values_list(
            "grave_site_type_id",
            "place_id",
            "access_level",
            "updated_at",
        ).get(pk=grave_site.pk)
        type_values = GraveSiteType.objects.values_list(
            "name",
            "is_active",
        ).get(pk=self.system_type.pk)
        place_values = Place.objects.values_list(
            "name",
            "access_level",
            "updated_at",
        ).get(pk=self.place.pk)
        actor_values = get_user_model().objects.values_list(
            "is_active",
            "is_staff",
            "is_superuser",
        ).get(pk=actor.pk)
        permission_ids = set(
            actor.user_permissions.values_list("pk", flat=True)
        )
        object_counts = (
            GraveSite.objects.count(),
            GraveSiteType.objects.count(),
            Place.objects.count(),
            get_user_model().objects.count(),
        )

        list(get_visible_grave_sites(actor=actor))

        self.assertEqual(
            GraveSite.objects.values_list(
                "grave_site_type_id",
                "place_id",
                "access_level",
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
                "access_level",
                "updated_at",
            ).get(pk=self.place.pk),
            place_values,
        )
        self.assertEqual(
            get_user_model().objects.values_list(
                "is_active",
                "is_staff",
                "is_superuser",
            ).get(pk=actor.pk),
            actor_values,
        )
        self.assertEqual(
            set(actor.user_permissions.values_list("pk", flat=True)),
            permission_ids,
        )
        self.assertEqual(
            (
                GraveSite.objects.count(),
                GraveSiteType.objects.count(),
                Place.objects.count(),
                get_user_model().objects.count(),
            ),
            object_counts,
        )
