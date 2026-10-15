"""Actor-aware workflow žádostí a grantů soukromých příloh."""

from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .choices import (
    AttachmentAccessRequestStatus,
    AttachmentPrivacyStatus,
    FileStatus,
)
from .models import (
    Attachment,
    AttachmentAccessGrant,
    AttachmentAccessRequest,
    AttachmentLinkModel,
)
from .selectors import _get_context_visible_attachment_link

__all__ = (
    "approve_attachment_access_request",
    "deny_attachment_access_request",
    "request_attachment_access",
    "revoke_attachment_access_grant",
)

_ACTOR_DENIAL = "K této operaci se soukromou přílohou nemáte oprávnění."


def _error(key: str, message: str, code: str) -> NoReturn:
    raise ValidationError({key: ValidationError(message, code=code)})


def _load_active_actor(
    actor: AbstractBaseUser | AnonymousUser,
) -> AbstractBaseUser:
    user_model = get_user_model()
    if (
        not isinstance(actor, user_model)
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
    ):
        raise PermissionDenied(_ACTOR_DENIAL)
    try:
        return user_model._default_manager.select_for_update().get(
            pk=actor.pk,
            is_active=True,
        )
    except user_model.DoesNotExist as error:
        raise PermissionDenied(_ACTOR_DENIAL) from error


def _load_available_private_attachment(
    attachment_id: int,
    *,
    require_available: bool = True,
) -> Attachment:
    try:
        current = (
            Attachment.objects.select_for_update()
            .select_related("vault__owner")
            .get(pk=attachment_id)
        )
    except Attachment.DoesNotExist as error:
        _error(
            "attachment",
            "Soukromá příloha není dostupná.",
            "attachment_unavailable",
        )
    if current.privacy_status != AttachmentPrivacyStatus.PRIVATE:
        _error(
            "attachment",
            "Příloha není soukromá.",
            "attachment_not_private",
        )
    if require_available and (
        current.archived_at is not None
        or current.deleted_at is not None
        or current.file_status != FileStatus.AVAILABLE
    ):
        _error(
            "attachment",
            "Soukromá příloha není dostupná.",
            "attachment_unavailable",
        )
    return current


def _require_current_active_owner(
    *,
    actor: AbstractBaseUser,
    attachment: Attachment,
) -> None:
    if (
        attachment.vault.owner_id != actor.pk
        or not attachment.vault.owner.is_active
    ):
        raise PermissionDenied(_ACTOR_DENIAL)


def _active_grant_exists(*, attachment_id: int, grantee_id: int) -> bool:
    return AttachmentAccessGrant.objects.filter(
        attachment_id=attachment_id,
        grantee_id=grantee_id,
        revoked_at__isnull=True,
    ).exists()


def request_attachment_access(
    *,
    link: AttachmentLinkModel,
    actor: AbstractBaseUser | AnonymousUser,
    message: str = "",
) -> AttachmentAccessRequest:
    """Vytvoř žádost pouze přes čerstvě viditelný aktivní kontextový link."""

    with transaction.atomic():
        current_actor = _load_active_actor(actor)
        current_link = _get_context_visible_attachment_link(
            link=link,
            actor=current_actor,
            for_update=True,
        )
        attachment = _load_available_private_attachment(
            current_link.attachment_id
        )
        if attachment.vault.owner_id == current_actor.pk:
            _error(
                "actor",
                "Vlastník o přístup ke své příloze nežádá.",
                "attachment_owner_request",
            )
        if _active_grant_exists(
            attachment_id=attachment.pk,
            grantee_id=current_actor.pk,
        ):
            _error(
                "actor",
                "Aktivní přístup k příloze již existuje.",
                "attachment_grant_active",
            )
        if AttachmentAccessRequest.objects.filter(
            attachment_id=attachment.pk,
            requester_id=current_actor.pk,
            status=AttachmentAccessRequestStatus.PENDING,
        ).exists():
            _error(
                "request",
                "Žádost o přístup již čeká na rozhodnutí.",
                "attachment_request_pending",
            )
        try:
            with transaction.atomic():
                access_request = AttachmentAccessRequest.objects.create(
                    attachment=attachment,
                    requester=current_actor,
                    message=(message or "").strip(),
                )
        except IntegrityError as error:
            raise ValidationError(
                {
                    "request": ValidationError(
                        "Žádost o přístup již čeká na rozhodnutí.",
                        code="attachment_request_pending",
                    )
                }
            ) from error
        return access_request


def _load_request_for_owner(
    *,
    access_request: AttachmentAccessRequest,
    actor: AbstractBaseUser | AnonymousUser,
    require_available: bool,
) -> tuple[
    AttachmentAccessRequest,
    AbstractBaseUser,
    Attachment,
    AbstractBaseUser,
]:
    if (
        not isinstance(access_request, AttachmentAccessRequest)
        or access_request.pk is None
    ):
        _error(
            "request",
            "Žádost musí být uložená v databázi.",
            "attachment_request_unsaved",
        )
    current_actor = _load_active_actor(actor)
    try:
        current_request = (
            AttachmentAccessRequest.objects.select_for_update().get(
                pk=access_request.pk,
            )
        )
    except AttachmentAccessRequest.DoesNotExist as error:
        _error(
            "request",
            "Žádost musí být uložená v databázi.",
            "attachment_request_unsaved",
        )
    requester = (
        get_user_model()
        ._default_manager.select_for_update()
        .get(pk=current_request.requester_id)
    )
    attachment = _load_available_private_attachment(
        current_request.attachment_id,
        require_available=require_available,
    )
    _require_current_active_owner(actor=current_actor, attachment=attachment)
    return current_request, current_actor, attachment, requester


def approve_attachment_access_request(
    *,
    access_request: AttachmentAccessRequest,
    actor: AbstractBaseUser | AnonymousUser,
    decision_note: str = "",
) -> AttachmentAccessGrant:
    """Atomicky schval pending request a vytvoř jediný aktivní grant."""

    with transaction.atomic():
        current, current_actor, attachment, requester = (
            _load_request_for_owner(
                access_request=access_request,
                actor=actor,
                require_available=True,
            )
        )
        if current.status != AttachmentAccessRequestStatus.PENDING:
            _error(
                "request",
                "Žádost již nečeká na rozhodnutí.",
                "attachment_request_not_pending",
            )
        if not requester.is_active or requester.pk == attachment.vault.owner_id:
            _error(
                "requester",
                "Žadatel již nemůže získat přístup.",
                "attachment_requester_unavailable",
            )
        if _active_grant_exists(
            attachment_id=attachment.pk,
            grantee_id=requester.pk,
        ):
            _error(
                "grant",
                "Aktivní přístup k příloze již existuje.",
                "attachment_grant_active",
            )
        resolved_at = timezone.now()
        current.status = AttachmentAccessRequestStatus.APPROVED
        current.resolved_at = resolved_at
        current.resolved_by = current_actor
        current.decision_note = (decision_note or "").strip()
        current.save(
            update_fields={
                "status",
                "resolved_at",
                "resolved_by",
                "decision_note",
                "updated_at",
            }
        )
        try:
            with transaction.atomic():
                grant = AttachmentAccessGrant.objects.create(
                    attachment=attachment,
                    grantee=requester,
                    request=current,
                    granted_at=resolved_at,
                    granted_by=current_actor,
                )
        except IntegrityError as error:
            raise ValidationError(
                {
                    "grant": ValidationError(
                        "Aktivní přístup k příloze již existuje.",
                        code="attachment_grant_active",
                    )
                }
            ) from error
        return grant


def deny_attachment_access_request(
    *,
    access_request: AttachmentAccessRequest,
    actor: AbstractBaseUser | AnonymousUser,
    decision_note: str = "",
) -> AttachmentAccessRequest:
    """Uzavři ownerem autorizovaný pending request bez vytvoření grantu."""

    with transaction.atomic():
        current, current_actor, _, _ = _load_request_for_owner(
            access_request=access_request,
            actor=actor,
            require_available=False,
        )
        if current.status != AttachmentAccessRequestStatus.PENDING:
            _error(
                "request",
                "Žádost již nečeká na rozhodnutí.",
                "attachment_request_not_pending",
            )
        current.status = AttachmentAccessRequestStatus.DENIED
        current.resolved_at = timezone.now()
        current.resolved_by = current_actor
        current.decision_note = (decision_note or "").strip()
        current.save(
            update_fields={
                "status",
                "resolved_at",
                "resolved_by",
                "decision_note",
                "updated_at",
            }
        )
        return current


def revoke_attachment_access_grant(
    *,
    grant: AttachmentAccessGrant,
    actor: AbstractBaseUser | AnonymousUser,
    reason: str = "",
) -> AttachmentAccessGrant:
    """Ukonči aktivní grant bez odstranění workflow historie."""

    if not isinstance(grant, AttachmentAccessGrant) or grant.pk is None:
        _error(
            "grant",
            "Grant musí být uložený v databázi.",
            "attachment_grant_unsaved",
        )
    with transaction.atomic():
        current_actor = _load_active_actor(actor)
        try:
            current = AttachmentAccessGrant.objects.select_for_update().get(
                pk=grant.pk,
            )
        except AttachmentAccessGrant.DoesNotExist as error:
            _error(
                "grant",
                "Grant musí být uložený v databázi.",
                "attachment_grant_unsaved",
            )
        attachment = _load_available_private_attachment(
            current.attachment_id,
            require_available=False,
        )
        _require_current_active_owner(actor=current_actor, attachment=attachment)
        if current.revoked_at is not None:
            _error(
                "grant",
                "Grant již není aktivní.",
                "attachment_grant_not_active",
            )
        current.revoked_at = timezone.now()
        current.revoked_by = current_actor
        current.revoke_reason = (reason or "").strip()
        current.save(
            update_fields={
                "revoked_at",
                "revoked_by",
                "revoke_reason",
                "updated_at",
            }
        )
        return current
