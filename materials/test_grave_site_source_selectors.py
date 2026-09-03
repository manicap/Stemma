from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel, VerificationStatus
from places.models import GraveSite, GraveSiteType, Place

from .choices import SourceSupport
from .models import GraveSiteSource, Source, SourceRole, SourceType
from .selectors import (
    get_grave_site_source_links,
    get_visible_grave_site_source_links,
)


class GraveSiteSourceSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        for selector, names in (
            (get_grave_site_source_links, ("grave_site",)),
            (
                get_visible_grave_site_source_links,
                ("grave_site", "actor"),
            ),
        ):
            parameters = signature(selector).parameters
            self.assertEqual(tuple(parameters), names)
            self.assertTrue(
                all(
                    value.kind is Parameter.KEYWORD_ONLY
                    for value in parameters.values()
                )
            )


class GraveSiteSourceSelectorTests(TestCase):
    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(username="author")
        self.grave_site_type = GraveSiteType.objects.get(code="grave")
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.grave_site = self.make_grave_site()
        self.source_type = SourceType.objects.create(
            code="archive",
            name="Archiv",
        )
        self.role = SourceRole.objects.create(
            code="evidence",
            name="Doklad",
            sort_order=10,
        )

    def make_grave_site(self, **overrides) -> GraveSite:
        values = {
            "grave_site_type": self.grave_site_type,
            "place": self.place,
            "created_by": self.author,
        }
        values.update(overrides)
        return GraveSite.objects.create(**values)

    def source(self, title: str, **overrides) -> Source:
        values = {
            "source_type": self.source_type,
            "title": title,
            "created_by": self.author,
        }
        values.update(overrides)
        return Source.objects.create(**values)

    def link(self, title: str, **overrides) -> GraveSiteSource:
        values = {
            "grave_site": self.grave_site,
            "source": self.source(title),
            "role": self.role,
            "support_strength": SourceSupport.CONFIRMS,
            "created_by": self.author,
        }
        values.update(overrides)
        return GraveSiteSource.objects.create(**values)

    @staticmethod
    def user(username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def visible(self, actor, *, grave_site=None) -> QuerySet:
        return get_visible_grave_site_source_links(
            grave_site=grave_site or self.grave_site,
            actor=actor,
        )

    def test_permissionless_history_excludes_only_deleted_link(self) -> None:
        active = self.link("Aktivní")
        archived = self.link("Archivovaná", archived_at=timezone.now())
        hidden = self.link("Skrytá", access_level=AccessLevel.ADMIN_ONLY)
        deleted_source = self.link(
            "Odstraněný zdroj",
            source=self.source("Odstraněný", deleted_at=timezone.now()),
        )
        self.link("Odstraněná vazba", deleted_at=timezone.now())

        self.assertEqual(
            list(get_grave_site_source_links(grave_site=self.grave_site)),
            [active, archived, hidden, deleted_source],
        )

    def test_invalid_grave_site_has_stable_error_in_both_selectors(self) -> None:
        missing = self.make_grave_site(location_text="Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        for grave_site in (GraveSite(), missing, object()):
            for selector, arguments in (
                (get_grave_site_source_links, {"grave_site": grave_site}),
                (
                    get_visible_grave_site_source_links,
                    {"grave_site": grave_site, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["grave_site"][0].code,
                        "grave_site_unsaved",
                    )

    def test_target_enforces_access_and_lifecycle(self) -> None:
        manager = self.user("manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))
        self.link("Zdroj")
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(len(self.visible(AnonymousUser())), 1)
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            archived_at=None,
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)

        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(manager)
        with self.assertRaises(PermissionDenied):
            self.visible(self.user("superuser", is_superuser=True))

    def test_non_policy_dimensions_do_not_hide_result(self) -> None:
        link = self.link("Historický kontext")
        GraveSite.objects.filter(pk=self.grave_site.pk).update(
            status="destroyed",
            verification_status=VerificationStatus.DISPUTED,
        )
        Place.objects.filter(pk=self.place.pk).update(
            access_level=AccessLevel.ADMIN_ONLY,
            archived_at=timezone.now(),
            deleted_at=timezone.now(),
        )
        GraveSiteType.objects.filter(pk=self.grave_site_type.pk).update(
            is_active=False
        )
        SourceType.objects.filter(pk=self.source_type.pk).update(is_active=False)
        SourceRole.objects.filter(pk=self.role.pk).update(is_active=False)

        self.assertEqual(list(self.visible(AnonymousUser())), [link])

    def test_result_requires_visible_active_link_and_source(self) -> None:
        public = self.link("Veřejný")
        restricted_link = self.link(
            "Omezená vazba",
            access_level=AccessLevel.RESTRICTED,
        )
        restricted_source = self.link(
            "Omezený zdroj",
            source=self.source(
                "Omezený",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        self.link("Archivovaná vazba", archived_at=timezone.now())
        self.link(
            "Archivovaný zdroj",
            source=self.source("Archiv", archived_at=timezone.now()),
        )
        manager = self.user("access-manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))

        self.assertEqual(list(self.visible(AnonymousUser())), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted_link, restricted_source],
        )

    def test_actor_state_and_invalid_actor_use_central_policy(self) -> None:
        link = self.link("Omezený", access_level=AccessLevel.RESTRICTED)
        actor = self.user("stale-actor")
        actor.user_permissions.add(self.permission("view_restricted_content"))
        self.assertEqual(list(self.visible(actor)), [link])
        actor.user_permissions.remove(self.permission("view_restricted_content"))
        self.assertEqual(list(self.visible(actor)), [])
        get_user_model().objects.filter(pk=actor.pk).update(is_superuser=True)
        self.assertEqual(list(self.visible(actor)), [link])
        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=False,
            is_active=False,
        )
        self.assertEqual(list(self.visible(actor)), [])

        for invalid, code in (
            (None, "actor_invalid"),
            (object(), "actor_invalid"),
            (get_user_model()(username="unsaved"), "actor_unsaved"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError) as context:
                    self.visible(invalid)
                self.assertEqual(
                    context.exception.error_dict["actor"][0].code,
                    code,
                )

    def test_shared_source_does_not_reveal_hidden_grave_site(self) -> None:
        shared = self.source("Sdílený")
        public_link = GraveSiteSource.objects.create(
            grave_site=self.grave_site,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )
        hidden = self.make_grave_site(
            location_text="Skryté",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        GraveSiteSource.objects.create(
            grave_site=hidden,
            source=shared,
            role=self.role,
            support_strength=SourceSupport.CONFIRMS,
        )

        self.assertEqual(list(self.visible(AnonymousUser())), [public_link])
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), grave_site=hidden)

    def test_order_preload_and_lazy_filters_cover_complete_path(self) -> None:
        later_role = SourceRole.objects.create(
            code="later",
            name="Pozdější",
            sort_order=20,
        )
        later = self.link("Pozdější", role=later_role)
        earlier = self.link("Dřívější")
        with CaptureQueriesContext(connection) as captured:
            result = list(self.visible(AnonymousUser()))
            for link in result:
                str(link.grave_site.grave_site_type)
                str(link.grave_site.place)
                link.grave_site.created_by.username
                str(link.source.source_type)
                link.source.created_by.username
                str(link.role)
                link.created_by.username
        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(captured), 3)

        now = timezone.now()
        cases = (
            (
                GraveSite,
                self.grave_site.pk,
                {"access_level": AccessLevel.RESTRICTED},
                None,
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                GraveSite,
                self.grave_site.pk,
                {"archived_at": now},
                [earlier, later],
                {"archived_at": None},
            ),
            (
                GraveSite,
                self.grave_site.pk,
                {"deleted_at": now},
                None,
                {"deleted_at": None},
            ),
            (
                GraveSiteSource,
                earlier.pk,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                GraveSiteSource,
                earlier.pk,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                GraveSiteSource,
                earlier.pk,
                {"deleted_at": now},
                [later],
                {"deleted_at": None},
            ),
            (
                Source,
                earlier.source_id,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Source,
                earlier.source_id,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                Source,
                earlier.source_id,
                {"deleted_at": now},
                [later],
                {"deleted_at": None},
            ),
        )
        for model, object_id, change, expected, reset in cases:
            with self.subTest(model=model.__name__):
                queryset = self.visible(AnonymousUser())
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), expected or [])
                model.objects.filter(pk=object_id).update(**reset)
