"""Centrální privacy policy soukromých příloh."""

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Exists, OuterRef, Q

from .choices import AttachmentAccessRequestStatus, AttachmentPrivacyStatus
from .models import Attachment, AttachmentAccessGrant

__all__ = (
    "can_access_private_attachment",
    "get_attachment_privacy_filter",
)


def _load_active_actor(
    actor: AbstractBaseUser | AnonymousUser,
) -> AbstractBaseUser | None:
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
    ):
        return None
    return user_model._default_manager.filter(
        pk=actor.pk,
        is_active=True,
    ).first()


def can_access_private_attachment(
    *,
    attachment: Attachment,
    actor: AbstractBaseUser | AnonymousUser,
) -> bool:
    """Ověř čerstvý owner/grant kontrakt bez nahrazení kontextové policy."""

    if not isinstance(attachment, Attachment) or attachment.pk is None:
        return False
    current_actor = _load_active_actor(actor)
    if current_actor is None:
        return False
    current = (
        Attachment.objects.select_related("vault__owner")
        .filter(pk=attachment.pk)
        .first()
    )
    if (
        current is None
        or current.privacy_status != AttachmentPrivacyStatus.PRIVATE
    ):
        return False
    if (
        current.vault.owner_id == current_actor.pk
        and current.vault.owner.is_active
    ):
        return True
    return AttachmentAccessGrant.objects.filter(
        attachment_id=current.pk,
        grantee_id=current_actor.pk,
        grantee__is_active=True,
        revoked_at__isnull=True,
        request__status=AttachmentAccessRequestStatus.APPROVED,
        request__attachment_id=current.pk,
        request__requester_id=current_actor.pk,
    ).exists()


def get_attachment_privacy_filter(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    prefix: str = "attachment",
) -> Q:
    """Sestav SQL privacy filtr pro kontextový Attachment link queryset."""

    field = f"{prefix}__" if prefix else ""
    condition = Q(
        **{
            f"{field}privacy_status": AttachmentPrivacyStatus.STANDARD,
        }
    )
    current_actor = _load_active_actor(actor)
    if current_actor is None:
        return condition
    private = {f"{field}privacy_status": AttachmentPrivacyStatus.PRIVATE}
    owner = {
        f"{field}vault__owner_id": current_actor.pk,
        f"{field}vault__owner__is_active": True,
    }
    attachment_id = f"{prefix}_id" if prefix else "pk"
    valid_grant = AttachmentAccessGrant.objects.filter(
        attachment_id=OuterRef(attachment_id),
        grantee_id=current_actor.pk,
        grantee__is_active=True,
        revoked_at__isnull=True,
        request__status=AttachmentAccessRequestStatus.APPROVED,
        request__attachment_id=OuterRef(attachment_id),
        request__requester_id=current_actor.pk,
    )
    return condition | (
        Q(**private) & (Q(**owner) | Q(Exists(valid_grant)))
    )
