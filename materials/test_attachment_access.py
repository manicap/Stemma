from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from common.models import TimestampedModel
from people.models import Person

from .access_policy import can_access_private_attachment
from .access_services import (
    approve_attachment_access_request,
    deny_attachment_access_request,
    request_attachment_access,
    revoke_attachment_access_grant,
)
from .choices import (
    AttachmentAccessRequestStatus,
    AttachmentPrivacyStatus,
    FileStatus,
)
from .models import (
    Attachment,
    AttachmentAccessGrant,
    AttachmentAccessRequest,
    AttachmentCategory,
    AttachmentRole,
    PersonAttachment,
)
from .selectors import get_visible_person_attachment_links
from .services import get_or_create_owned_vault


class AttachmentAccessRequestStatusTests(SimpleTestCase):
    def test_fixed_values_are_exact(self) -> None:
        self.assertTrue(
            issubclass(AttachmentAccessRequestStatus, models.TextChoices)
        )
        self.assertEqual(
            AttachmentAccessRequestStatus.values,
            ["pending", "approved", "denied", "cancelled"],
        )


class AttachmentAccessFixture(TestCase):
    sha256 = "a" * 64

    def setUp(self) -> None:
        self.owner = self.user("owner")
        self.requester = self.user("requester")
        self.other = self.user("other")
        self.vault = get_or_create_owned_vault(owner=self.owner)
        self.category = AttachmentCategory.objects.create(
            code="access-document",
            name="Dokument",
        )
        self.role = AttachmentRole.objects.create(
            code="access-evidence",
            name="Doklad",
        )
        self.person = Person.objects.create(first_name="Anna")
        self.attachment = self.make_attachment()
        self.link = PersonAttachment.objects.create(
            person=self.person,
            attachment=self.attachment,
            role=self.role,
        )

    @staticmethod
    def user(username: str, **values: object):
        return get_user_model().objects.create_user(
            username=username,
            **values,
        )

    def make_attachment(self, **values: object) -> Attachment:
        data = {
            "vault": self.vault,
            "category": self.category,
            "original_filename": "private.pdf",
            "storage_key": f"opaque-{Attachment.objects.count()}",
            "mime_type": "application/pdf",
            "size_bytes": 123,
            "sha256": self.sha256,
            "file_status": FileStatus.AVAILABLE,
            "privacy_status": AttachmentPrivacyStatus.PRIVATE,
        }
        data.update(values)
        return Attachment.objects.create(**data)

    def request(self, actor=None) -> AttachmentAccessRequest:
        return request_attachment_access(
            link=self.link,
            actor=actor or self.requester,
            message="  Prosím o přístup.  ",
        )

    def assert_code(
        self,
        exception: ValidationError,
        key: str,
        code: str,
    ) -> None:
        self.assertEqual(exception.error_dict[key][0].code, code)


class AttachmentAccessModelTests(AttachmentAccessFixture):
    def test_models_are_history_only_and_not_registered_in_admin(self) -> None:
        self.assertEqual(
            AttachmentAccessRequest.__bases__,
            (TimestampedModel, models.Model),
        )
        self.assertEqual(
            AttachmentAccessGrant.__bases__,
            (TimestampedModel, models.Model),
        )
        self.assertFalse(hasattr(AttachmentAccessRequest(), "archived_at"))
        self.assertFalse(hasattr(AttachmentAccessGrant(), "deleted_at"))
        self.assertFalse(admin.site.is_registered(AttachmentAccessRequest))
        self.assertFalse(admin.site.is_registered(AttachmentAccessGrant))
        self.assertEqual(
            str(AttachmentAccessRequest()),
            "Žádost o přístup k soukromé příloze",
        )
        self.assertEqual(
            str(AttachmentAccessGrant()),
            "Grant přístupu k soukromé příloze",
        )

    def test_foreign_keys_are_protected_and_request_is_one_to_one(self) -> None:
        for model, field_name in (
            (AttachmentAccessRequest, "attachment"),
            (AttachmentAccessRequest, "requester"),
            (AttachmentAccessRequest, "resolved_by"),
            (AttachmentAccessGrant, "attachment"),
            (AttachmentAccessGrant, "grantee"),
            (AttachmentAccessGrant, "request"),
            (AttachmentAccessGrant, "granted_by"),
            (AttachmentAccessGrant, "revoked_by"),
        ):
            with self.subTest(model=model.__name__, field=field_name):
                field = model._meta.get_field(field_name)
                self.assertIs(field.remote_field.on_delete, models.PROTECT)
        self.assertTrue(
            AttachmentAccessGrant._meta.get_field("request").one_to_one
        )

    def test_database_allows_only_one_pending_request_per_pair(self) -> None:
        if connection.vendor == "sqlite":
            self.assertFalse(connection.features.has_select_for_update)
        self.request()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttachmentAccessRequest.objects.create(
                    attachment=self.attachment,
                    requester=self.requester,
                )

    def test_request_resolution_metadata_constraint(self) -> None:
        now = timezone.now()
        invalid = (
            {"resolved_at": now, "resolved_by": self.owner},
            {
                "status": AttachmentAccessRequestStatus.APPROVED,
                "resolved_at": now,
            },
            {
                "status": AttachmentAccessRequestStatus.DENIED,
                "resolved_by": self.owner,
            },
        )
        for index, values in enumerate(invalid):
            with self.subTest(index=index):
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        AttachmentAccessRequest.objects.create(
                            attachment=self.attachment,
                            requester=self.requester,
                            **values,
                        )

    def test_database_allows_only_one_active_grant_per_pair(self) -> None:
        if connection.vendor == "sqlite":
            self.assertFalse(connection.features.has_select_for_update)
        first_request = self.request()
        first = approve_attachment_access_request(
            access_request=first_request,
            actor=self.owner,
        )
        second_request = AttachmentAccessRequest.objects.create(
            attachment=self.attachment,
            requester=self.requester,
            status=AttachmentAccessRequestStatus.APPROVED,
            resolved_at=timezone.now(),
            resolved_by=self.owner,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AttachmentAccessGrant.objects.create(
                    attachment=self.attachment,
                    grantee=self.requester,
                    request=second_request,
                    granted_at=timezone.now(),
                    granted_by=self.owner,
                )
        self.assertTrue(
            AttachmentAccessGrant.objects.filter(pk=first.pk).exists()
        )

    def test_grant_revocation_metadata_constraint(self) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        grant.revoked_at = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                grant.save(update_fields={"revoked_at"})

    def test_grant_model_validation_rejects_cross_row_mismatch(self) -> None:
        access_request = self.request()
        access_request.status = AttachmentAccessRequestStatus.APPROVED
        access_request.resolved_at = timezone.now()
        access_request.resolved_by = self.owner
        access_request.save()
        mismatched = AttachmentAccessGrant(
            attachment=self.attachment,
            grantee=self.other,
            request=access_request,
            granted_at=timezone.now(),
            granted_by=self.owner,
        )
        with self.assertRaises(ValidationError) as context:
            mismatched.full_clean()
        self.assert_code(
            context.exception,
            "request",
            "attachment_grant_request_mismatch",
        )

    def test_history_foreign_keys_are_protected(self) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        with self.assertRaises(ProtectedError):
            access_request.delete()
        with self.assertRaises(ProtectedError):
            self.requester.delete()
        self.assertTrue(AttachmentAccessGrant.objects.filter(pk=grant.pk).exists())


class AttachmentAccessServiceTests(AttachmentAccessFixture):
    def test_valid_request_uses_visible_link_and_normalizes_message(self) -> None:
        access_request = self.request()
        self.assertEqual(access_request.attachment, self.attachment)
        self.assertEqual(access_request.requester, self.requester)
        self.assertEqual(access_request.message, "Prosím o přístup.")
        self.assertEqual(
            access_request.status,
            AttachmentAccessRequestStatus.PENDING,
        )

    def test_request_rejects_standard_owner_grant_and_duplicate(self) -> None:
        Attachment.objects.filter(pk=self.attachment.pk).update(
            privacy_status=AttachmentPrivacyStatus.STANDARD
        )
        with self.assertRaises(ValidationError) as standard:
            self.request()
        self.assert_code(
            standard.exception,
            "attachment",
            "attachment_not_private",
        )
        Attachment.objects.filter(pk=self.attachment.pk).update(
            privacy_status=AttachmentPrivacyStatus.PRIVATE
        )
        with self.assertRaises(ValidationError) as owner:
            self.request(self.owner)
        self.assert_code(owner.exception, "actor", "attachment_owner_request")

        pending = self.request()
        with self.assertRaises(ValidationError) as duplicate:
            self.request()
        self.assert_code(
            duplicate.exception,
            "request",
            "attachment_request_pending",
        )
        grant = approve_attachment_access_request(
            access_request=pending,
            actor=self.owner,
        )
        with self.assertRaises(ValidationError) as granted:
            self.request()
        self.assert_code(granted.exception, "actor", "attachment_grant_active")
        self.assertIsNotNone(grant.pk)

    def test_request_rejects_anonymous_inactive_hidden_and_unavailable(self) -> None:
        for actor in (AnonymousUser(), self.user("inactive", is_active=False)):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    request_attachment_access(link=self.link, actor=actor)

        PersonAttachment.objects.filter(pk=self.link.pk).update(
            deleted_at=timezone.now()
        )
        with self.assertRaises(PermissionDenied):
            self.request()
        PersonAttachment.objects.filter(pk=self.link.pk).update(deleted_at=None)

        for values in (
            {"archived_at": timezone.now()},
            {"deleted_at": timezone.now()},
            {"file_status": FileStatus.MISSING},
        ):
            Attachment.objects.filter(pk=self.attachment.pk).update(**values)
            with self.subTest(values=values):
                with self.assertRaises(PermissionDenied):
                    self.request()
            Attachment.objects.filter(pk=self.attachment.pk).update(
                archived_at=None,
                deleted_at=None,
                file_status=FileStatus.AVAILABLE,
            )

    def test_staff_and_superuser_do_not_bypass_hidden_context(self) -> None:
        staff = self.user("staff", is_staff=True)
        superuser = self.user("super", is_superuser=True)
        PersonAttachment.objects.filter(pk=self.link.pk).update(
            deleted_at=timezone.now()
        )
        for actor in (staff, superuser):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    request_attachment_access(link=self.link, actor=actor)

    def test_owner_approve_creates_matching_grant_and_second_fails(self) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
            decision_note="  Schváleno.  ",
        )
        access_request.refresh_from_db()
        self.assertEqual(
            access_request.status,
            AttachmentAccessRequestStatus.APPROVED,
        )
        self.assertEqual(access_request.resolved_by, self.owner)
        self.assertEqual(access_request.decision_note, "Schváleno.")
        self.assertEqual(grant.attachment, self.attachment)
        self.assertEqual(grant.grantee, self.requester)
        self.assertEqual(grant.request, access_request)
        self.assertEqual(grant.granted_by, self.owner)
        self.assertEqual(AttachmentAccessGrant.objects.count(), 1)

        with self.assertRaises(ValidationError) as repeated:
            approve_attachment_access_request(
                access_request=access_request,
                actor=self.owner,
            )
        self.assert_code(
            repeated.exception,
            "request",
            "attachment_request_not_pending",
        )
        self.assertEqual(AttachmentAccessGrant.objects.count(), 1)

    def test_owner_deny_closes_request_without_grant(self) -> None:
        access_request = self.request()
        denied = deny_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
            decision_note="  Ne.  ",
        )
        self.assertEqual(denied.status, AttachmentAccessRequestStatus.DENIED)
        self.assertEqual(denied.decision_note, "Ne.")
        self.assertFalse(AttachmentAccessGrant.objects.exists())

    def test_non_owner_staff_and_superuser_cannot_decide(self) -> None:
        access_request = self.request()
        staff = self.user("decision-staff", is_staff=True)
        superuser = self.user("decision-super", is_superuser=True)
        for actor in (self.other, staff, superuser):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    approve_attachment_access_request(
                        access_request=access_request,
                        actor=actor,
                    )
                with self.assertRaises(PermissionDenied):
                    deny_attachment_access_request(
                        access_request=access_request,
                        actor=actor,
                    )
        access_request.refresh_from_db()
        self.assertEqual(
            access_request.status,
            AttachmentAccessRequestStatus.PENDING,
        )

    def test_inactive_owner_cannot_decide_or_revoke(self) -> None:
        access_request = self.request()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            approve_attachment_access_request(
                access_request=access_request,
                actor=self.owner,
            )
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=True)
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            revoke_attachment_access_grant(grant=grant, actor=self.owner)

    def test_inactive_requester_cannot_be_approved(self) -> None:
        access_request = self.request()
        get_user_model().objects.filter(pk=self.requester.pk).update(
            is_active=False
        )
        with self.assertRaises(ValidationError) as context:
            approve_attachment_access_request(
                access_request=access_request,
                actor=self.owner,
            )
        self.assert_code(
            context.exception,
            "requester",
            "attachment_requester_unavailable",
        )

    def test_owner_revoke_preserves_approved_request_and_history(self) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        revoked = revoke_attachment_access_grant(
            grant=grant,
            actor=self.owner,
            reason="  Konec sdílení.  ",
        )
        self.assertIsNotNone(revoked.revoked_at)
        self.assertEqual(revoked.revoked_by, self.owner)
        self.assertEqual(revoked.revoke_reason, "Konec sdílení.")
        access_request.refresh_from_db()
        self.assertEqual(
            access_request.status,
            AttachmentAccessRequestStatus.APPROVED,
        )

        first_revoked_at = revoked.revoked_at
        with self.assertRaises(ValidationError) as repeated:
            revoke_attachment_access_grant(
                grant=grant,
                actor=self.owner,
            )
        self.assert_code(
            repeated.exception,
            "grant",
            "attachment_grant_not_active",
        )
        grant.refresh_from_db()
        self.assertEqual(grant.revoked_at, first_revoked_at)

    def test_non_owner_cannot_revoke_and_inactive_attachment_can_be_revoked(
        self,
    ) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        with self.assertRaises(PermissionDenied):
            revoke_attachment_access_grant(grant=grant, actor=self.other)
        Attachment.objects.filter(pk=self.attachment.pk).update(
            archived_at=timezone.now()
        )
        revoked = revoke_attachment_access_grant(
            grant=grant,
            actor=self.owner,
        )
        self.assertIsNotNone(revoked.revoked_at)

    def test_grant_policy_is_fresh_and_does_not_trust_inconsistent_request(
        self,
    ) -> None:
        access_request = self.request()
        grant = approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        self.assertTrue(
            can_access_private_attachment(
                attachment=self.attachment,
                actor=self.requester,
            )
        )
        AttachmentAccessRequest.objects.filter(pk=access_request.pk).update(
            status=AttachmentAccessRequestStatus.DENIED
        )
        self.assertFalse(
            can_access_private_attachment(
                attachment=self.attachment,
                actor=self.requester,
            )
        )
        AttachmentAccessRequest.objects.filter(pk=access_request.pk).update(
            status=AttachmentAccessRequestStatus.APPROVED
        )
        revoke_attachment_access_grant(grant=grant, actor=self.owner)
        self.assertFalse(
            can_access_private_attachment(
                attachment=self.attachment,
                actor=self.requester,
            )
        )

    def test_active_grant_extends_full_read_but_not_lifecycle(self) -> None:
        access_request = self.request()
        approve_attachment_access_request(
            access_request=access_request,
            actor=self.owner,
        )
        self.assertEqual(
            list(
                get_visible_person_attachment_links(
                    person=self.person,
                    actor=self.requester,
                )
            ),
            [self.link],
        )
        Attachment.objects.filter(pk=self.attachment.pk).update(
            archived_at=timezone.now()
        )
        self.assertEqual(
            list(
                get_visible_person_attachment_links(
                    person=self.person,
                    actor=self.requester,
                )
            ),
            [],
        )

    def test_historical_grants_do_not_duplicate_standard_selector_rows(
        self,
    ) -> None:
        Attachment.objects.filter(pk=self.attachment.pk).update(
            privacy_status=AttachmentPrivacyStatus.STANDARD
        )
        for index in range(2):
            decided_at = timezone.now()
            access_request = AttachmentAccessRequest.objects.create(
                attachment=self.attachment,
                requester=self.requester,
                status=AttachmentAccessRequestStatus.APPROVED,
                message=f"Historie {index}",
                resolved_at=decided_at,
                resolved_by=self.owner,
            )
            AttachmentAccessGrant.objects.create(
                attachment=self.attachment,
                grantee=self.requester,
                request=access_request,
                granted_at=decided_at,
                granted_by=self.owner,
                revoked_at=decided_at,
                revoked_by=self.owner,
            )
        self.assertEqual(
            list(
                get_visible_person_attachment_links(
                    person=self.person,
                    actor=self.requester,
                )
            ),
            [self.link],
        )
