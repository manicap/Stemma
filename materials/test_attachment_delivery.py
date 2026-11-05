from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.choices import AccessLevel
from events.models import Event, EventType
from health.models import HealthRecord, HealthRecordType
from people.models import Person, Relationship, RelationshipType
from places.models import GraveSite, GraveSiteType, Place, Residence, ResidenceType

from .access_services import (
    approve_attachment_access_request,
    request_attachment_access,
    revoke_attachment_access_grant,
)
from .choices import AttachmentPrivacyStatus, FileStatus
from .delivery import (
    AttachmentDeliveryUnavailable,
    get_attachment_delivery,
)
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    EventAttachment,
    GraveSiteAttachment,
    HealthRecordAttachment,
    PersonAttachment,
    ResidenceAttachment,
    RelationshipAttachment,
)
from .services import get_or_create_owned_vault
from .storage import ProtectedAttachmentStorage


class AttachmentDeliveryApiTests(SimpleTestCase):
    def test_context_contract_lists_only_actor_aware_link_types(self) -> None:
        expected = {
            "person": PersonAttachment,
            "event": EventAttachment,
            "health-record": HealthRecordAttachment,
            "relationship": RelationshipAttachment,
            "residence": ResidenceAttachment,
            "grave-site": GraveSiteAttachment,
        }

        from .delivery import _CONTEXTS

        self.assertEqual(
            {
                key: definition.link_model
                for key, definition in _CONTEXTS.items()
            },
            expected,
        )


class AttachmentDeliveryTests(TestCase):
    blob = b"%PDF-1.4\nminimal protected test blob\n%%EOF\n"
    storage_key = "a" * 64

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.settings_override = override_settings(
            PROTECTED_ATTACHMENTS_ROOT=self.temporary_directory.name,
            PROTECTED_ATTACHMENTS_FILE_PERMISSIONS=0o600,
            PROTECTED_ATTACHMENTS_DIRECTORY_PERMISSIONS=0o700,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.owner = self.user("delivery-owner")
        self.other = self.user("delivery-other")
        self.inactive = self.user("delivery-inactive", is_active=False)
        self.vault = get_or_create_owned_vault(owner=self.owner)
        self.category = AttachmentCategory.objects.create(
            code="delivery-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="delivery-evidence",
            name="Doklad",
        )
        self.person = Person.objects.create(first_name="Anna")
        self.attachment = Attachment.objects.create(
            vault=self.vault,
            category=self.category,
            original_filename="bezpečný dokument.pdf",
            storage_key=self.storage_key,
            mime_type="application/pdf",
            size_bytes=len(self.blob),
            sha256="b" * 64,
            file_status=FileStatus.AVAILABLE,
            privacy_status=AttachmentPrivacyStatus.PRIVATE,
        )
        self.link = PersonAttachment.objects.create(
            person=self.person,
            attachment=self.attachment,
            role=self.role,
        )
        ProtectedAttachmentStorage().write(
            self.vault,
            self.storage_key,
            BytesIO(self.blob),
        )

    @staticmethod
    def user(username: str, **values: object):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    def url(
        self,
        name: str = "open-attachment",
        *,
        context_type: str = "person",
        context_id: int | None = None,
        link_id: int | None = None,
    ) -> str:
        return reverse(
            f"materials:{name}",
            kwargs={
                "context_type": context_type,
                "context_id": context_id or self.person.pk,
                "link_id": link_id or self.link.pk,
            },
        )

    def response_content(self, response) -> bytes:
        return b"".join(response.streaming_content)

    def assert_delivery_status(self, expected: int, response) -> None:
        self.assertEqual(response.status_code, expected)
        if response.status_code == 200:
            self.response_content(response)

    def make_stored_attachment(self, marker: str) -> Attachment:
        storage_key = marker * 64
        attachment = Attachment.objects.create(
            vault=self.vault,
            category=self.category,
            original_filename=f"{marker}.pdf",
            storage_key=storage_key,
            mime_type="application/pdf",
            size_bytes=len(self.blob),
            sha256=marker * 64,
            file_status=FileStatus.AVAILABLE,
            privacy_status=AttachmentPrivacyStatus.PRIVATE,
        )
        ProtectedAttachmentStorage().write(
            self.vault,
            storage_key,
            BytesIO(self.blob),
        )
        return attachment

    def test_owner_can_open_and_download_private_blob(self) -> None:
        self.client.force_login(self.owner)

        inline = self.client.get(self.url())
        download = self.client.get(self.url("download-attachment"))

        self.assertEqual(inline.status_code, 200)
        self.assertEqual(self.response_content(inline), self.blob)
        self.assertTrue(inline["Content-Disposition"].startswith("inline;"))
        self.assertEqual(inline["Content-Type"], "application/pdf")
        self.assertEqual(inline["Cache-Control"], "private, no-store")
        self.assertEqual(inline["X-Content-Type-Options"], "nosniff")
        self.assertEqual(inline["Referrer-Policy"], "no-referrer")
        self.assertIn("Cookie", inline["Vary"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(self.response_content(download), self.blob)
        self.assertTrue(
            download["Content-Disposition"].startswith("attachment;")
        )

    def test_active_grantee_can_read_and_revocation_closes_delivery(self) -> None:
        access_request = request_attachment_access(
            link=self.link,
            actor=self.other,
        )
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        self.client.force_login(self.other)

        self.assert_delivery_status(200, self.client.get(self.url()))

        revoke_attachment_access_grant(grant=grant, actor=self.owner)
        self.assert_delivery_status(404, self.client.get(self.url()))

    def test_private_delivery_denies_anonymous_inactive_and_ungranted_users(
        self,
    ) -> None:
        self.assert_delivery_status(404, self.client.get(self.url()))

        self.client.force_login(self.inactive)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        for actor in (
            self.user("delivery-staff", is_staff=True),
            self.user("delivery-superuser", is_superuser=True),
        ):
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_standard_public_attachment_preserves_anonymous_public_policy(
        self,
    ) -> None:
        self.attachment.privacy_status = AttachmentPrivacyStatus.STANDARD
        self.attachment.save(update_fields={"privacy_status", "updated_at"})

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.response_content(response), self.blob)

    def test_modified_context_and_link_urls_fail_without_metadata_leak(
        self,
    ) -> None:
        self.client.force_login(self.owner)
        wrong_context = self.client.get(
            self.url(context_id=self.person.pk + 1000)
        )
        wrong_link = self.client.get(self.url(link_id=self.link.pk + 1000))
        unsupported = self.client.get(
            self.url(context_type="place")
        )

        for response in (wrong_context, wrong_link, unsupported):
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(
                response,
                self.storage_key,
                status_code=404,
            )
            self.assertNotContains(
                response,
                self.attachment.original_filename,
                status_code=404,
            )

    def test_attachment_and_link_lifecycle_are_fail_closed(self) -> None:
        self.client.force_login(self.owner)
        self.link.archived_at = timezone.now()
        self.link.save(update_fields={"archived_at", "updated_at"})
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.link.archived_at = None
        self.link.deleted_at = timezone.now()
        self.link.save(
            update_fields={"archived_at", "deleted_at", "updated_at"}
        )
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.link.deleted_at = None
        self.link.save(update_fields={"deleted_at", "updated_at"})
        self.attachment.archived_at = timezone.now()
        self.attachment.save(update_fields={"archived_at", "updated_at"})
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.attachment.archived_at = None
        self.attachment.deleted_at = timezone.now()
        self.attachment.save(
            update_fields={"archived_at", "deleted_at", "updated_at"}
        )
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_person_lifecycle_respects_existing_explicit_permissions(self) -> None:
        self.person.archived_at = timezone.now()
        self.person.save(update_fields={"archived_at", "updated_at"})
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.owner.user_permissions.add(
            Permission.objects.get(codename="view_archived_person")
        )
        self.assert_delivery_status(200, self.client.get(self.url()))

        self.person.archived_at = None
        self.person.deleted_at = timezone.now()
        self.person.save(
            update_fields={"archived_at", "deleted_at", "updated_at"}
        )
        self.assert_delivery_status(404, self.client.get(self.url()))

        self.owner.user_permissions.add(
            Permission.objects.get(codename="view_deleted_person")
        )
        self.assert_delivery_status(200, self.client.get(self.url()))

    def test_missing_status_or_physical_blob_is_not_delivered(self) -> None:
        self.client.force_login(self.owner)
        self.attachment.file_status = FileStatus.MISSING
        self.attachment.save(update_fields={"file_status", "updated_at"})
        self.assertEqual(self.client.get(self.url()).status_code, 404)

        self.attachment.file_status = FileStatus.AVAILABLE
        self.attachment.save(update_fields={"file_status", "updated_at"})
        ProtectedAttachmentStorage().delete(
            self.vault,
            self.storage_key,
        )
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, self.storage_key, status_code=404)

    def test_unsupported_mime_and_non_get_method_are_fail_closed(self) -> None:
        self.client.force_login(self.owner)
        self.attachment.mime_type = "text/html"
        self.attachment.save(update_fields={"mime_type", "updated_at"})
        self.assertEqual(self.client.get(self.url()).status_code, 404)
        self.assertEqual(self.client.post(self.url()).status_code, 405)

    def test_unknown_privacy_value_is_fail_closed(self) -> None:
        Attachment.objects.filter(pk=self.attachment.pk).update(
            privacy_status="unknown",
        )
        self.client.force_login(self.owner)

        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_all_supported_contexts_use_their_real_actor_aware_policy(
        self,
    ) -> None:
        self.owner.user_permissions.add(
            Permission.objects.get(codename="view_restricted_content")
        )
        place = Place.objects.create(
            name="Praha",
            normalized_name="praha-delivery",
        )
        event_type = EventType.objects.create(
            code="delivery-event",
            name="Událost",
        )
        event = Event.objects.create(event_type=event_type, place=place)
        event_link = EventAttachment.objects.create(
            event=event,
            attachment=self.make_stored_attachment("c"),
            role=self.role,
        )

        health_type = HealthRecordType.objects.create(
            code="delivery-health",
            name="Zdravotní záznam",
        )
        health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=health_type,
            title="Záznam",
        )
        other_health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=health_type,
            title="Jiný záznam",
        )
        health_link = HealthRecordAttachment.objects.create(
            health_record=health_record,
            attachment=self.make_stored_attachment("d"),
            role=self.role,
        )

        other_person = Person.objects.create(first_name="Berta")
        relationship_type = RelationshipType.objects.create(
            code="delivery-relationship",
            name="Vazba",
            forward_label_male="vazba",
            forward_label_female="vazba",
            forward_label_unknown="vazba",
            reverse_label_male="vazba",
            reverse_label_female="vazba",
            reverse_label_unknown="vazba",
            is_symmetric=True,
        )
        relationship = Relationship.objects.create(
            relationship_type=relationship_type,
            person_a=self.person,
            person_b=other_person,
        )
        relationship_link = RelationshipAttachment.objects.create(
            relationship=relationship,
            attachment=self.make_stored_attachment("e"),
            role=self.role,
        )

        residence_type = ResidenceType.objects.create(
            code="delivery-residence",
            name="Bydliště",
        )
        residence = Residence.objects.create(
            person=self.person,
            residence_type=residence_type,
            place=place,
        )
        residence_link = ResidenceAttachment.objects.create(
            residence=residence,
            attachment=self.make_stored_attachment("f"),
            role=self.role,
        )

        grave_site = GraveSite.objects.create(
            grave_site_type=GraveSiteType.objects.get(code="grave"),
            place=place,
        )
        grave_link = GraveSiteAttachment.objects.create(
            grave_site=grave_site,
            attachment=self.make_stored_attachment("1"),
            role=self.role,
        )
        contexts = (
            ("event", event.pk, event_link.pk),
            ("health-record", health_record.pk, health_link.pk),
            ("relationship", relationship.pk, relationship_link.pk),
            ("residence", residence.pk, residence_link.pk),
            ("grave-site", grave_site.pk, grave_link.pk),
        )
        self.client.force_login(self.owner)

        for context_type, context_id, link_id in contexts:
            with self.subTest(context_type=context_type):
                self.assert_delivery_status(
                    200,
                    self.client.get(
                        self.url(
                            context_type=context_type,
                            context_id=context_id,
                            link_id=link_id,
                        )
                    ),
                )
        self.assertEqual(
            self.client.get(
                self.url(
                    context_type="health-record",
                    context_id=other_health_record.pk,
                    link_id=health_link.pk,
                )
            ).status_code,
            404,
        )

    def test_target_link_and_attachment_access_layers_are_all_required(
        self,
    ) -> None:
        self.client.force_login(self.owner)
        for instance in (self.person, self.link, self.attachment):
            instance.access_level = AccessLevel.RESTRICTED
            instance.save(update_fields={"access_level", "updated_at"})
            with self.subTest(model=type(instance).__name__):
                self.assertEqual(self.client.get(self.url()).status_code, 404)
            instance.access_level = AccessLevel.PUBLIC
            instance.save(update_fields={"access_level", "updated_at"})

        self.owner.user_permissions.add(
            Permission.objects.get(codename="view_restricted_content")
        )
        self.person.access_level = AccessLevel.RESTRICTED
        self.link.access_level = AccessLevel.RESTRICTED
        self.attachment.access_level = AccessLevel.RESTRICTED
        for instance in (self.person, self.link, self.attachment):
            instance.save(update_fields={"access_level", "updated_at"})
        self.assert_delivery_status(200, self.client.get(self.url()))

    def test_service_uses_same_sanitized_error_for_unavailable_delivery(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            AttachmentDeliveryUnavailable,
            "Příloha není dostupná",
        ):
            get_attachment_delivery(
                context_type="person",
                context_id=self.person.pk,
                link_id=self.link.pk,
                actor=AnonymousUser(),
            )
