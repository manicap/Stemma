from dataclasses import fields

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from people.models import Person
from events.models import Event, EventType
from health.models import HealthRecord, HealthRecordType
from people.models import Relationship, RelationshipType
from places.models import (
    GraveSite,
    GraveSiteType,
    Place,
    Residence,
    ResidenceType,
)

from .access_services import (
    approve_attachment_access_request,
    request_attachment_access,
    revoke_attachment_access_grant,
)
from .choices import AttachmentPrivacyStatus, FileStatus
from .models import (
    Attachment,
    AttachmentCategory,
    AttachmentRole,
    EventAttachment,
    GraveSiteAttachment,
    HealthRecordAttachment,
    PersonAttachment,
    PlaceAttachment,
    RelationshipAttachment,
    ResidenceAttachment,
)
from .selectors import (
    AttachmentMetadataPresentation,
    PrivateAttachmentPlaceholder,
    get_attachment_link_presentation,
)
from .services import get_or_create_owned_vault


class AttachmentPresentationTests(TestCase):
    def setUp(self) -> None:
        self.owner = get_user_model().objects.create_user(username="owner")
        self.reader = get_user_model().objects.create_user(username="reader")
        self.staff = get_user_model().objects.create_user(
            username="staff",
            is_staff=True,
        )
        self.superuser = get_user_model().objects.create_user(
            username="superuser",
            is_superuser=True,
        )
        self.vault = get_or_create_owned_vault(owner=self.owner)
        self.category = AttachmentCategory.objects.create(
            code="presentation-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="presentation-evidence",
            name="Doklad",
        )
        self.person = Person.objects.create(first_name="Anna")
        self.attachment = Attachment.objects.create(
            vault=self.vault,
            category=self.category,
            display_name="Tajný dokument",
            description="Citlivý popis",
            original_filename="secret.pdf",
            storage_key="never-present-this-key",
            mime_type="application/pdf",
            size_bytes=456,
            sha256="b" * 64,
            file_status=FileStatus.AVAILABLE,
            privacy_status=AttachmentPrivacyStatus.PRIVATE,
            technical_metadata={"pages": 2},
            created_by=self.owner,
        )
        self.link = PersonAttachment.objects.create(
            person=self.person,
            attachment=self.attachment,
            role=self.role,
        )

    def presentation(self, actor=None):
        return get_attachment_link_presentation(
            link=self.link,
            actor=actor or self.reader,
        )

    def grant_reader(self):
        access_request = request_attachment_access(
            link=self.link,
            actor=self.reader,
        )
        return approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )

    def test_unauthorized_private_presentation_is_only_fixed_placeholder(self) -> None:
        presentation = self.presentation()
        self.assertEqual(presentation, PrivateAttachmentPlaceholder())
        self.assertEqual(presentation.label, "Soukromý dokument")
        self.assertTrue(presentation.is_redacted)
        self.assertEqual(
            tuple(field.name for field in fields(presentation)),
            ("label",),
        )
        serialized = repr(presentation)
        for secret in (
            "secret.pdf",
            "application/pdf",
            "456",
            "b" * 64,
            "never-present-this-key",
            self.owner.username,
            "pages",
        ):
            self.assertNotIn(secret, serialized)

    def test_owner_and_active_grantee_receive_safe_full_metadata(self) -> None:
        for actor in (self.owner,):
            presentation = self.presentation(actor)
            self.assertIsInstance(
                presentation,
                AttachmentMetadataPresentation,
            )
            self.assertFalse(presentation.is_redacted)
            self.assertEqual(presentation.original_filename, "secret.pdf")
            self.assertEqual(presentation.mime_type, "application/pdf")
            self.assertEqual(presentation.size_bytes, 456)
            self.assertEqual(presentation.sha256, "b" * 64)
            self.assertEqual(dict(presentation.technical_metadata), {"pages": 2})
            self.assertFalse(hasattr(presentation, "storage_key"))
        self.grant_reader()
        granted = self.presentation(self.reader)
        self.assertIsInstance(granted, AttachmentMetadataPresentation)
        self.assertEqual(granted.original_filename, "secret.pdf")

    def test_staff_and_superuser_are_not_private_bypass(self) -> None:
        for actor in (self.staff, self.superuser):
            with self.subTest(actor=actor):
                self.assertEqual(
                    self.presentation(actor),
                    PrivateAttachmentPlaceholder(),
                )

    def test_revoked_grant_is_immediately_redacted(self) -> None:
        grant = self.grant_reader()
        self.assertIsInstance(
            self.presentation(self.reader),
            AttachmentMetadataPresentation,
        )
        revoke_attachment_access_grant(grant=grant, actor=self.owner)
        self.assertEqual(
            self.presentation(self.reader),
            PrivateAttachmentPlaceholder(),
        )

    def test_standard_attachment_presentation_keeps_ordinary_metadata(self) -> None:
        Attachment.objects.filter(pk=self.attachment.pk).update(
            privacy_status=AttachmentPrivacyStatus.STANDARD
        )
        presentation = self.presentation(self.reader)
        self.assertIsInstance(presentation, AttachmentMetadataPresentation)
        self.assertEqual(presentation.label, "Tajný dokument")
        self.assertEqual(presentation.original_filename, "secret.pdf")
        self.assertFalse(hasattr(presentation, "storage_key"))

    def test_hidden_link_returns_no_placeholder(self) -> None:
        PersonAttachment.objects.filter(pk=self.link.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.presentation(self.reader)

    def test_grant_does_not_bypass_link_or_attachment_lifecycle_and_status(
        self,
    ) -> None:
        self.grant_reader()
        mutations = (
            (PersonAttachment, self.link.pk, {"archived_at": timezone.now()}),
            (Attachment, self.attachment.pk, {"archived_at": timezone.now()}),
            (Attachment, self.attachment.pk, {"deleted_at": timezone.now()}),
            (
                Attachment,
                self.attachment.pk,
                {"file_status": FileStatus.MISSING},
            ),
        )
        for model, pk, values in mutations:
            model.objects.filter(pk=pk).update(**values)
            with self.subTest(model=model.__name__, values=values):
                with self.assertRaises(PermissionDenied):
                    self.presentation(self.reader)
            PersonAttachment.objects.filter(pk=self.link.pk).update(
                archived_at=None
            )
            Attachment.objects.filter(pk=self.attachment.pk).update(
                archived_at=None,
                deleted_at=None,
                file_status=FileStatus.AVAILABLE,
            )

    def test_unsupported_place_link_fails_closed(self) -> None:
        place = Place.objects.create(name="Praha", normalized_name="praha")
        place_link = PlaceAttachment.objects.create(
            place=place,
            attachment=self.attachment,
            role=self.role,
        )
        with self.assertRaises(PermissionDenied):
            get_attachment_link_presentation(
                link=place_link,
                actor=self.owner,
            )

    def test_all_approved_actor_aware_contexts_can_return_redacted_placeholder(
        self,
    ) -> None:
        event_type = EventType.objects.create(
            code="presentation-event",
            name="Událost",
        )
        event = Event.objects.create(event_type=event_type)
        person_b = Person.objects.create(first_name="Berta")
        relationship_type = RelationshipType.objects.create(
            code="presentation-relationship",
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
            person_b=person_b,
        )
        place = Place.objects.create(name="Brno", normalized_name="brno")
        residence_type = ResidenceType.objects.create(
            code="presentation-residence",
            name="Bydliště",
        )
        residence = Residence(
            person=self.person,
            residence_type=residence_type,
            place=place,
        )
        residence.full_clean()
        residence.save()
        grave_site = GraveSite.objects.create(
            grave_site_type=GraveSiteType.objects.get(code="grave"),
            place=place,
        )
        health_record = HealthRecord.objects.create(
            person=self.person,
            record_type=HealthRecordType.objects.create(
                code="presentation-health",
                name="Záznam",
            ),
        )
        self.reader.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="accounts",
                codename="view_restricted_content",
            )
        )
        links = (
            EventAttachment.objects.create(
                event=event,
                attachment=self.attachment,
                role=self.role,
            ),
            RelationshipAttachment.objects.create(
                relationship=relationship,
                attachment=self.attachment,
                role=self.role,
            ),
            ResidenceAttachment.objects.create(
                residence=residence,
                attachment=self.attachment,
                role=self.role,
            ),
            GraveSiteAttachment.objects.create(
                grave_site=grave_site,
                attachment=self.attachment,
                role=self.role,
            ),
            HealthRecordAttachment.objects.create(
                health_record=health_record,
                attachment=self.attachment,
                role=self.role,
            ),
        )
        for link in links:
            with self.subTest(link=type(link).__name__):
                self.assertEqual(
                    get_attachment_link_presentation(
                        link=link,
                        actor=self.reader,
                    ),
                    PrivateAttachmentPlaceholder(),
                )
