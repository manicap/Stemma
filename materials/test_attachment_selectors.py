from inspect import Parameter, signature
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from people.models import Person

from . import selectors
from .choices import FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    PersonAttachment,
)
from .selectors import (
    get_person_attachment_links,
    get_visible_person_attachment_links,
)


class PersonAttachmentSelectorApiTests(SimpleTestCase):
    def test_public_api_and_keyword_only_parameters(self) -> None:
        self.assertEqual(
            selectors.__all__,
            (
                "get_event_attachment_links",
                "get_event_source_links",
                "get_grave_site_attachment_links",
                "get_grave_site_source_links",
                "get_person_attachment_links",
                "get_person_name_source_links",
                "get_residence_attachment_links",
                "get_residence_source_links",
                "get_relationship_attachment_links",
                "get_relationship_source_links",
                "get_visible_event_attachment_links",
                "get_visible_event_source_links",
                "get_visible_grave_site_attachment_links",
                "get_visible_grave_site_source_links",
                "get_visible_health_record_attachment_links",
                "get_visible_health_record_source_links",
                "get_visible_person_attachment_links",
                "get_visible_person_name_source_links",
                "get_visible_residence_attachment_links",
                "get_visible_residence_source_links",
                "get_visible_relationship_attachment_links",
                "get_visible_relationship_source_links",
            ),
        )
        expectations = (
            (get_person_attachment_links, ("person",)),
            (get_visible_person_attachment_links, ("person", "actor")),
        )
        for selector, expected_names in expectations:
            with self.subTest(selector=selector.__name__):
                parameters = signature(selector).parameters
                self.assertEqual(tuple(parameters), expected_names)
                self.assertTrue(
                    all(
                        parameter.kind is Parameter.KEYWORD_ONLY
                        for parameter in parameters.values()
                    )
                )


class PersonAttachmentSelectorTests(TestCase):
    sha256 = "a" * 64

    def setUp(self) -> None:
        self.person = Person.objects.create(
            first_name="Anna",
            last_name="Testovací",
        )
        self.category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
        )

    @staticmethod
    def create_user(username: str, **values: object):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def grant(self, actor, *codenames: str) -> None:
        actor.user_permissions.add(
            *(self.permission(codename) for codename in codenames)
        )

    def create_attachment(self, key: str, **overrides: object) -> Attachment:
        values = {
            "category": self.category,
            "original_filename": f"{key}.pdf",
            "storage_key": f"attachments/{key}.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "sha256": self.sha256,
            "file_status": FileStatus.AVAILABLE,
        }
        values.update(overrides)
        return Attachment.objects.create(**values)

    def create_link(self, key: str, **overrides: object) -> PersonAttachment:
        values = {
            "person": self.person,
            "attachment": self.create_attachment(key),
            "role": self.role,
        }
        values.update(overrides)
        return PersonAttachment.objects.create(**values)

    def visible(self, actor, *, person: Person | None = None) -> QuerySet:
        return get_visible_person_attachment_links(
            person=person or self.person,
            actor=actor,
        )

    def test_permissionless_selector_returns_full_non_deleted_history(self) -> None:
        active = self.create_link("active")
        archived = self.create_link("archived", archived_at=timezone.now())
        hidden = self.create_link(
            "hidden",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        missing = self.create_link(
            "missing",
            attachment=self.create_attachment(
                "missing-file",
                file_status=FileStatus.MISSING,
                deleted_at=timezone.now(),
            ),
        )
        deleted = self.create_link("deleted", deleted_at=timezone.now())

        result = list(get_person_attachment_links(person=self.person))

        self.assertEqual(result, [active, archived, hidden, missing])
        self.assertNotIn(deleted, result)

    def test_invalid_person_uses_stable_error(self) -> None:
        missing = Person.objects.create(first_name="Chybějící")
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for person in (Person(first_name="Neuložená"), missing, object()):
            with self.subTest(person=person):
                with self.assertRaises(ValidationError) as context:
                    get_person_attachment_links(person=person)
                error = context.exception.error_dict["person"][0]
                self.assertEqual(error.code, "person_unsaved")

    def test_each_access_level_is_evaluated_once(self) -> None:
        with patch(
            "materials.selectors.can_view_access_level",
            wraps=selectors.can_view_access_level,
        ) as permission_check:
            self.visible(AnonymousUser())

        self.assertEqual(permission_check.call_count, 4)
        self.assertEqual(
            {
                call.kwargs["access_level"]
                for call in permission_check.call_args_list
            },
            set(AccessLevel.values),
        )

    def test_invalid_actor_uses_central_stable_errors(self) -> None:
        for actor, code in (
            (None, "actor_invalid"),
            (object(), "actor_invalid"),
            (get_user_model()(username="unsaved"), "actor_unsaved"),
        ):
            with self.subTest(actor=actor):
                with self.assertRaises(ValidationError) as context:
                    self.visible(actor)
                self.assertEqual(
                    context.exception.error_dict["actor"][0].code,
                    code,
                )

    def test_input_person_access_and_lifecycle_are_enforced(self) -> None:
        ordinary = self.create_user("ordinary")
        manager = self.create_user("manager")
        self.grant(
            manager,
            "view_restricted_content",
            "view_archived_person",
            "view_deleted_person",
        )
        admin_manager = self.create_user("admin-manager")
        self.grant(admin_manager, "view_admin_only_content")
        staff = self.create_user("staff", is_staff=True)
        inactive = self.create_user("inactive", is_active=False)
        superuser = self.create_user("superuser", is_superuser=True)
        now = timezone.now()
        cases = (
            (AnonymousUser(), AccessLevel.PUBLIC, None, None, True),
            (AnonymousUser(), AccessLevel.AUTHENTICATED, None, None, False),
            (ordinary, AccessLevel.AUTHENTICATED, None, None, True),
            (ordinary, AccessLevel.RESTRICTED, None, None, False),
            (manager, AccessLevel.RESTRICTED, None, None, True),
            (ordinary, AccessLevel.ADMIN_ONLY, None, None, False),
            (admin_manager, AccessLevel.ADMIN_ONLY, None, None, True),
            (staff, AccessLevel.RESTRICTED, None, None, False),
            (inactive, AccessLevel.AUTHENTICATED, None, None, False),
            (superuser, AccessLevel.ADMIN_ONLY, None, None, True),
            (ordinary, AccessLevel.PUBLIC, now, None, False),
            (manager, AccessLevel.PUBLIC, now, None, True),
            (ordinary, AccessLevel.PUBLIC, None, now, False),
            (manager, AccessLevel.PUBLIC, None, now, True),
        )
        for index, (actor, access, archived, deleted, allowed) in enumerate(cases):
            person = Person.objects.create(
                first_name=f"Osoba {index}",
                access_level=access,
                archived_at=archived,
                deleted_at=deleted,
            )
            with self.subTest(index=index):
                if allowed:
                    self.assertIsInstance(self.visible(actor, person=person), QuerySet)
                else:
                    with self.assertRaises(PermissionDenied):
                        self.visible(actor, person=person)

    def test_invalid_stored_person_access_fails_closed(self) -> None:
        Person.objects.filter(pk=self.person.pk).update(
            access_level="invalid_historical_value",
        )

        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

    def test_result_requires_all_three_access_layers(self) -> None:
        public = self.create_link("public")
        restricted_link = self.create_link(
            "restricted-link",
            access_level=AccessLevel.RESTRICTED,
        )
        restricted_attachment = self.create_link(
            "restricted-attachment",
            attachment=self.create_attachment(
                "restricted-file",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        manager = self.create_user("access-manager")
        self.grant(manager, "view_restricted_content")

        self.assertEqual(list(self.visible(AnonymousUser())), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted_link, restricted_attachment],
        )

        Person.objects.filter(pk=self.person.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

    def test_result_requires_active_available_non_deleted_layers(self) -> None:
        available = self.create_link("available")
        self.create_link(
            "archived-link",
            archived_at=timezone.now(),
        )
        self.create_link(
            "archived-attachment",
            attachment=self.create_attachment(
                "archived-file",
                archived_at=timezone.now(),
            ),
        )
        for status in (
            FileStatus.PENDING,
            FileStatus.MISSING,
            FileStatus.QUARANTINED,
        ):
            self.create_link(
                status,
                attachment=self.create_attachment(
                    f"file-{status}",
                    file_status=status,
                ),
            )
        self.create_link(
            "deleted-file-link",
            attachment=self.create_attachment(
                "deleted-file",
                deleted_at=timezone.now(),
            ),
        )
        self.create_link("deleted-link", deleted_at=timezone.now())

        self.assertEqual(
            list(self.visible(AnonymousUser())),
            [available],
        )

    def test_inactive_category_and_role_do_not_hide_available_result(self) -> None:
        link = self.create_link("inactive-lookups")
        AttachmentCategory.objects.filter(pk=self.category.pk).update(
            is_active=False,
        )
        AttachmentRole.objects.filter(pk=self.role.pk).update(is_active=False)

        self.assertEqual(list(self.visible(AnonymousUser())), [link])

    def test_actor_state_and_permissions_are_loaded_fresh_for_each_call(self) -> None:
        link = self.create_link(
            "restricted",
            access_level=AccessLevel.RESTRICTED,
        )
        actor = self.create_user("stale-actor")
        current_actor = get_user_model().objects.get(pk=actor.pk)
        self.grant(current_actor, "view_restricted_content")
        self.assertEqual(list(self.visible(actor)), [link])

        current_actor.user_permissions.remove(
            self.permission("view_restricted_content")
        )
        self.assertEqual(list(self.visible(actor)), [])

        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=True,
        )
        self.assertEqual(list(self.visible(actor)), [link])
        get_user_model().objects.filter(pk=actor.pk).update(
            is_superuser=False,
            is_active=False,
        )
        self.assertEqual(list(self.visible(actor)), [])

    def test_queryset_is_ordered_and_has_no_result_n_plus_one(self) -> None:
        second_role = AttachmentRole.objects.create(
            code="portrait",
            name="Portrét",
            sort_order=10,
        )
        later = self.create_link("later", sort_order=20)
        earlier = self.create_link(
            "earlier",
            role=second_role,
            sort_order=10,
        )

        queryset = self.visible(AnonymousUser())
        self.assertIsInstance(queryset, QuerySet)
        with CaptureQueriesContext(connection) as queries:
            result = list(queryset)
            for link in result:
                str(link.person)
                str(link.attachment.category)
                str(link.role)
                link.attachment.created_by
                link.created_by

        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(queries), 1)

    def test_result_filters_against_fresh_database_state(self) -> None:
        link = self.create_link("fresh")
        queryset = self.visible(AnonymousUser())
        PersonAttachment.objects.filter(pk=link.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )

        self.assertEqual(list(queryset), [])
