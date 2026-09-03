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
from people.models import Person, Relationship, RelationshipType

from .choices import FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    RelationshipAttachment,
)
from .selectors import (
    get_relationship_attachment_links,
    get_visible_relationship_attachment_links,
)


class RelationshipAttachmentSelectorApiTests(SimpleTestCase):
    def test_parameters_are_keyword_only(self) -> None:
        for selector, names in (
            (get_relationship_attachment_links, ("relationship",)),
            (
                get_visible_relationship_attachment_links,
                ("relationship", "actor"),
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


class RelationshipAttachmentSelectorTests(TestCase):
    sha256 = "a" * 64

    def setUp(self) -> None:
        self.author = get_user_model().objects.create_user(username="author")
        self.person_a = Person.objects.create(first_name="Anna")
        self.person_b = Person.objects.create(first_name="Berta")
        self.relationship_type = RelationshipType.objects.create(
            code="test_attachment_relationship",
            name="Testovací vazba",
            forward_label_male="vazba",
            forward_label_female="vazba",
            forward_label_unknown="vazba",
            reverse_label_male="vazba",
            reverse_label_female="vazba",
            reverse_label_unknown="vazba",
            is_symmetric=True,
        )
        self.relationship = self.make_relationship(
            self.person_a,
            self.person_b,
        )
        self.category = AttachmentCategory.objects.create(
            code="document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="evidence",
            name="Doklad",
            sort_order=10,
        )

    def make_relationship(self, person_a, person_b, **overrides) -> Relationship:
        values = {
            "relationship_type": self.relationship_type,
            "person_a": person_a,
            "person_b": person_b,
            "created_by": self.author,
        }
        values.update(overrides)
        return Relationship.objects.create(**values)

    def attachment(self, key: str, **overrides) -> Attachment:
        values = {
            "category": self.category,
            "original_filename": f"{key}.pdf",
            "storage_key": f"attachments/{key}.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 100,
            "sha256": self.sha256,
            "file_status": FileStatus.AVAILABLE,
            "created_by": self.author,
        }
        values.update(overrides)
        return Attachment.objects.create(**values)

    def link(self, key: str, **overrides) -> RelationshipAttachment:
        values = {
            "relationship": self.relationship,
            "attachment": self.attachment(key),
            "role": self.role,
            "created_by": self.author,
        }
        values.update(overrides)
        return RelationshipAttachment.objects.create(**values)

    @staticmethod
    def user(username: str, **values):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    @staticmethod
    def permission(codename: str) -> Permission:
        return Permission.objects.get(codename=codename)

    def visible(self, actor, *, relationship=None) -> QuerySet:
        return get_visible_relationship_attachment_links(
            relationship=relationship or self.relationship,
            actor=actor,
        )

    def test_permissionless_history_excludes_only_deleted_link(self) -> None:
        active = self.link("active")
        archived = self.link("archived", archived_at=timezone.now())
        hidden = self.link("hidden", access_level=AccessLevel.ADMIN_ONLY)
        unavailable = self.link(
            "missing",
            attachment=self.attachment(
                "missing-file",
                file_status=FileStatus.MISSING,
                deleted_at=timezone.now(),
            ),
        )
        self.link("deleted", deleted_at=timezone.now())

        self.assertEqual(
            list(get_relationship_attachment_links(relationship=self.relationship)),
            [active, archived, hidden, unavailable],
        )

    def test_invalid_relationship_has_stable_error_in_both_selectors(self) -> None:
        missing = self.make_relationship(
            Person.objects.create(first_name="Cyril"),
            Person.objects.create(first_name="Dana"),
        )
        missing_pk = missing.pk
        missing.delete()
        missing.pk = missing_pk
        for relationship in (Relationship(), missing, object()):
            for selector, arguments in (
                (
                    get_relationship_attachment_links,
                    {"relationship": relationship},
                ),
                (
                    get_visible_relationship_attachment_links,
                    {"relationship": relationship, "actor": AnonymousUser()},
                ),
            ):
                with self.subTest(selector=selector.__name__):
                    with self.assertRaises(ValidationError) as context:
                        selector(**arguments)
                    self.assertEqual(
                        context.exception.error_dict["relationship"][0].code,
                        "relationship_unsaved",
                    )

    def test_target_requires_visible_relationship_and_both_people(self) -> None:
        manager = self.user("manager")
        manager.user_permissions.add(
            self.permission("view_restricted_content"),
            self.permission("view_archived_person"),
        )
        self.link("attachment")
        Relationship.objects.filter(pk=self.relationship.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(len(self.visible(AnonymousUser())), 1)
        Relationship.objects.filter(pk=self.relationship.pk).update(
            archived_at=None,
            access_level=AccessLevel.RESTRICTED,
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)

        Person.objects.filter(pk=self.person_b.pk).update(
            archived_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser())
        self.assertEqual(len(self.visible(manager)), 1)
        Person.objects.filter(pk=self.person_b.pk).update(
            archived_at=None,
            deleted_at=timezone.now(),
        )
        with self.assertRaises(PermissionDenied):
            self.visible(manager)
        with self.assertRaises(PermissionDenied):
            self.visible(self.user("superuser", is_superuser=True))

        Person.objects.filter(pk=self.person_b.pk).update(deleted_at=None)
        Relationship.objects.filter(pk=self.relationship.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.visible(manager)

    def test_result_requires_visible_active_available_layers(self) -> None:
        public = self.link("public")
        restricted_link = self.link(
            "restricted-link",
            access_level=AccessLevel.RESTRICTED,
        )
        restricted_attachment = self.link(
            "restricted-attachment",
            attachment=self.attachment(
                "restricted-file",
                access_level=AccessLevel.RESTRICTED,
            ),
        )
        self.link("archived-link", archived_at=timezone.now())
        self.link(
            "archived-attachment",
            attachment=self.attachment(
                "archived-file",
                archived_at=timezone.now(),
            ),
        )
        for status in (
            FileStatus.PENDING,
            FileStatus.MISSING,
            FileStatus.QUARANTINED,
        ):
            self.link(
                status,
                attachment=self.attachment(f"file-{status}", file_status=status),
            )
        manager = self.user("access-manager")
        manager.user_permissions.add(self.permission("view_restricted_content"))

        self.assertEqual(list(self.visible(AnonymousUser())), [public])
        self.assertEqual(
            list(self.visible(manager)),
            [public, restricted_link, restricted_attachment],
        )

    def test_actor_state_and_permissions_are_loaded_fresh_for_each_call(self) -> None:
        link = self.link(
            "restricted",
            access_level=AccessLevel.RESTRICTED,
        )
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

    def test_inactive_category_and_role_do_not_hide_available_result(self) -> None:
        link = self.link("inactive-lookups")
        AttachmentCategory.objects.filter(pk=self.category.pk).update(
            is_active=False
        )
        AttachmentRole.objects.filter(pk=self.role.pk).update(is_active=False)

        self.assertEqual(list(self.visible(AnonymousUser())), [link])

    def test_shared_attachment_does_not_reveal_hidden_relationship(self) -> None:
        shared = self.attachment("shared")
        public_link = RelationshipAttachment.objects.create(
            relationship=self.relationship,
            attachment=shared,
            role=self.role,
        )
        hidden_relationship = self.make_relationship(
            Person.objects.create(first_name="Eva"),
            Person.objects.create(
                first_name="František",
                access_level=AccessLevel.ADMIN_ONLY,
            ),
        )
        RelationshipAttachment.objects.create(
            relationship=hidden_relationship,
            attachment=shared,
            role=self.role,
        )

        self.assertEqual(list(self.visible(AnonymousUser())), [public_link])
        with self.assertRaises(PermissionDenied):
            self.visible(AnonymousUser(), relationship=hidden_relationship)

    def test_order_preload_and_lazy_filters_cover_complete_path(self) -> None:
        later = self.link("later", sort_order=20)
        earlier = self.link("earlier", sort_order=10)
        with CaptureQueriesContext(connection) as captured:
            result = list(self.visible(AnonymousUser()))
            for link in result:
                str(link.relationship.relationship_type)
                str(link.relationship.person_a)
                str(link.relationship.person_b)
                link.relationship.created_by.username
                str(link.attachment.category)
                link.attachment.created_by.username
                str(link.role)
                link.created_by.username
        self.assertEqual(result, [earlier, later])
        self.assertEqual(len(captured), 3)

        now = timezone.now()
        cases = (
            (
                Person,
                self.person_a.pk,
                {"archived_at": now},
                None,
                {"archived_at": None},
            ),
            (
                Person,
                self.person_b.pk,
                {"deleted_at": now},
                None,
                {"deleted_at": None},
            ),
            (
                Person,
                self.person_b.pk,
                {"access_level": AccessLevel.RESTRICTED},
                None,
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Relationship,
                self.relationship.pk,
                {"access_level": AccessLevel.RESTRICTED},
                None,
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Relationship,
                self.relationship.pk,
                {"deleted_at": now},
                None,
                {"deleted_at": None},
            ),
            (
                RelationshipAttachment,
                earlier.pk,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                RelationshipAttachment,
                earlier.pk,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                Attachment,
                earlier.attachment_id,
                {"access_level": AccessLevel.RESTRICTED},
                [later],
                {"access_level": AccessLevel.PUBLIC},
            ),
            (
                Attachment,
                earlier.attachment_id,
                {"archived_at": now},
                [later],
                {"archived_at": None},
            ),
            (
                Attachment,
                earlier.attachment_id,
                {"deleted_at": now},
                [later],
                {"deleted_at": None},
            ),
            (
                Attachment,
                earlier.attachment_id,
                {"file_status": FileStatus.MISSING},
                [later],
                {"file_status": FileStatus.AVAILABLE},
            ),
        )
        for model, object_id, change, expected, reset in cases:
            with self.subTest(model=model.__name__):
                queryset = self.visible(AnonymousUser())
                model.objects.filter(pk=object_id).update(**change)
                self.assertEqual(list(queryset), expected or [])
                model.objects.filter(pk=object_id).update(**reset)
