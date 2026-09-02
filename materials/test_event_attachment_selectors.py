from inspect import Parameter, signature

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from common.choices import AccessLevel
from events.models import Event, EventType
from places.models import Place

from .choices import FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    EventAttachment,
)
from .selectors import (
    get_event_attachment_links,
    get_visible_event_attachment_links,
)


class EventAttachmentSelectorApiTests(SimpleTestCase):
    def test_selectors_have_exact_keyword_only_parameters(self) -> None:
        expectations = (
            (get_event_attachment_links, ("event",)),
            (get_visible_event_attachment_links, ("event", "actor")),
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


class EventAttachmentSelectorTests(TestCase):
    sha256 = "b" * 64

    def setUp(self) -> None:
        self.uploader = get_user_model().objects.create_user(
            username="event-uploader",
        )
        self.place = Place.objects.create(
            name="Praha",
            normalized_name="praha",
        )
        self.event_type = EventType.objects.create(
            code="attachment_event",
            name="Událost s přílohou",
        )
        self.event = Event.objects.create(
            event_type=self.event_type,
            place=self.place,
            created_by=self.uploader,
        )
        self.category = AttachmentCategory.objects.create(
            code="event_document",
            name="Dokument události",
        )
        self.role = AttachmentRole.objects.create(
            code="event_evidence",
            name="Doklad události",
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

    def create_attachment(self, key: str, **overrides: object) -> Attachment:
        values = {
            "category": self.category,
            "original_filename": f"{key}.pdf",
            "storage_key": f"attachments/events/{key}.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "sha256": self.sha256,
            "file_status": FileStatus.AVAILABLE,
            "created_by": self.uploader,
        }
        values.update(overrides)
        return Attachment.objects.create(**values)

    def create_link(self, key: str, **overrides: object) -> EventAttachment:
        values = {
            "event": self.event,
            "attachment": self.create_attachment(key),
            "role": self.role,
            "created_by": self.uploader,
        }
        values.update(overrides)
        return EventAttachment.objects.create(**values)

    def visible(self, actor, *, event: Event | None = None) -> QuerySet:
        return get_visible_event_attachment_links(
            event=event or self.event,
            actor=actor,
        )

    def test_permissionless_selector_returns_non_deleted_link_history(self) -> None:
        active = self.create_link("active")
        archived = self.create_link("archived", archived_at=timezone.now())
        hidden = self.create_link(
            "hidden",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        deleted = self.create_link("deleted", deleted_at=timezone.now())

        queryset = get_event_attachment_links(event=self.event)
        self.assertIsInstance(queryset, QuerySet)
        self.assertEqual(
            list(queryset),
            [active, archived, hidden],
        )
        self.assertNotIn(
            deleted,
            get_event_attachment_links(event=self.event),
        )

    def test_invalid_event_uses_stable_error(self) -> None:
        missing = Event.objects.create(event_type=self.event_type)
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk

        for event in (Event(), missing, object()):
            for selector, arguments in (
                (get_event_attachment_links, {"event": event}),
                (
                    get_visible_event_attachment_links,
                    {"event": event, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(event=event, selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["event"][0].code,
                        "event_unsaved",
                    )

    def test_inactive_related_lookups_do_not_hide_available_result(self) -> None:
        link = self.create_link("inactive-lookups")
        EventType.objects.filter(pk=self.event_type.pk).update(is_active=False)
        AttachmentCategory.objects.filter(pk=self.category.pk).update(
            is_active=False,
        )
        AttachmentRole.objects.filter(pk=self.role.pk).update(is_active=False)

        self.assertEqual(list(self.visible(AnonymousUser())), [link])

    def test_input_event_uses_access_lifecycle_and_fresh_state(self) -> None:
        restricted_actor = self.create_user("restricted-event")
        restricted_actor.user_permissions.add(
            self.permission("view_restricted_content")
        )
        restricted = Event.objects.create(
            event_type=self.event_type,
            access_level=AccessLevel.RESTRICTED,
        )
        archived = Event.objects.create(
            event_type=self.event_type,
            archived_at=timezone.now(),
        )
        deleted = Event.objects.create(
            event_type=self.event_type,
            deleted_at=timezone.now(),
        )

        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), event=restricted)
        self.assertIsInstance(
            self.visible(restricted_actor, event=restricted),
            QuerySet,
        )
        for event in (archived, deleted):
            with self.assertRaises(PermissionDenied):
                self.visible(restricted_actor, event=event)

        Event.objects.filter(pk=self.event.pk).update(
            access_level="invalid_historical_value",
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

        Event.objects.filter(pk=self.event.pk).update(
            access_level=AccessLevel.PUBLIC,
            archived_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

        Event.objects.filter(pk=self.event.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())

    def test_result_requires_visible_active_available_layers(self) -> None:
        available = self.create_link("available")
        self.create_link(
            "hidden-link",
            access_level=AccessLevel.RESTRICTED,
        )
        self.create_link(
            "hidden-attachment",
            attachment=self.create_attachment(
                "restricted-file",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        self.create_link("archived-link", archived_at=timezone.now())
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
        self.create_link("deleted-link", deleted_at=timezone.now())
        self.create_link(
            "deleted-attachment",
            attachment=self.create_attachment(
                "deleted-file",
                deleted_at=timezone.now(),
            ),
        )

        self.assertEqual(list(self.visible(AnonymousUser())), [available])

    def test_central_actor_semantics_control_results(self) -> None:
        public = self.create_link("public")
        restricted = self.create_link(
            "restricted",
            access_level=AccessLevel.RESTRICTED,
        )
        authenticated = self.create_link(
            "authenticated",
            access_level=AccessLevel.AUTHENTICATED,
        )
        admin_only = self.create_link(
            "admin-only",
            access_level=AccessLevel.ADMIN_ONLY,
        )
        staff = self.create_user("event-staff", is_staff=True)
        manager = self.create_user("event-manager")
        manager.user_permissions.add(
            self.permission("view_restricted_content")
        )
        admin_manager = self.create_user("event-admin-manager")
        admin_manager.user_permissions.add(
            self.permission("view_admin_only_content")
        )
        inactive = self.create_user("event-inactive", is_active=False)
        superuser = self.create_user("event-super", is_superuser=True)

        self.assertEqual(list(self.visible(staff)), [public, authenticated])
        self.assertEqual(list(self.visible(inactive)), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted, authenticated],
        )
        self.assertEqual(
            list(self.visible(admin_manager)),
            [public, authenticated, admin_only],
        )
        self.assertEqual(
            list(self.visible(superuser)),
            [public, restricted, authenticated, admin_only],
        )

    def test_result_is_ordered_and_preloaded_without_n_plus_one(self) -> None:
        later = self.create_link("later", sort_order=20)
        earlier = self.create_link("earlier", sort_order=10)
        queryset = self.visible(AnonymousUser())

        with CaptureQueriesContext(connection) as queries:
            result = list(queryset)
            for link in result:
                str(link.event.event_type)
                link.event.place
                link.event.created_by
                str(link.attachment.category)
                link.attachment.created_by
                str(link.role)
                link.created_by

        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(queries), 1)

    def test_lazy_result_filters_fresh_database_state(self) -> None:
        link = self.create_link("fresh")
        queryset = self.visible(AnonymousUser())
        EventAttachment.objects.filter(pk=link.pk).update(
            access_level=AccessLevel.RESTRICTED,
        )

        self.assertEqual(list(queryset), [])

        EventAttachment.objects.filter(pk=link.pk).update(
            access_level=AccessLevel.PUBLIC,
        )
        queryset = self.visible(AnonymousUser())
        Event.objects.filter(pk=self.event.pk).update(
            archived_at=timezone.now(),
        )
        self.assertEqual(list(queryset), [])

        Event.objects.filter(pk=self.event.pk).update(archived_at=None)
        queryset = self.visible(AnonymousUser())
        Attachment.objects.filter(pk=link.attachment_id).update(
            file_status=FileStatus.QUARANTINED,
        )
        self.assertEqual(list(queryset), [])
