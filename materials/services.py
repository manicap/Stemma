"""Transakční doménové služby explicitních vazeb příloh."""

from dataclasses import dataclass
from typing import Any, NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction

from common.choices import AccessLevel
from events.models import Event
from people.models import Person, Relationship
from places.models import GraveSite, Place, Residence

from .models import (
    Attachment,
    AttachmentLinkModel,
    AttachmentRole,
    EventAttachment,
    GraveSiteAttachment,
    PersonAttachment,
    PlaceAttachment,
    RelationshipAttachment,
    ResidenceAttachment,
)

__all__ = (
    "AttachmentLinkInput",
    "create_event_attachment",
    "create_grave_site_attachment",
    "create_person_attachment",
    "create_place_attachment",
    "create_relationship_attachment",
    "create_residence_attachment",
    "update_event_attachment",
    "update_grave_site_attachment",
    "update_person_attachment",
    "update_place_attachment",
    "update_relationship_attachment",
    "update_residence_attachment",
)


@dataclass(frozen=True, slots=True)
class AttachmentLinkInput:
    """Úplný snapshot společných editovatelných údajů vazby přílohy."""

    attachment: Attachment
    role: AttachmentRole
    context_description: str = ""
    sort_order: int = 0
    is_primary: bool = False
    access_level: str = AccessLevel.PUBLIC


@dataclass(frozen=True, slots=True)
class _LinkSpec:
    model: type[AttachmentLinkModel]
    target_model: type[models.Model]
    target_field: str
    target_label: str


_PERSON = _LinkSpec(PersonAttachment, Person, "person", "Osoba")
_EVENT = _LinkSpec(EventAttachment, Event, "event", "Událost")
_RELATIONSHIP = _LinkSpec(
    RelationshipAttachment,
    Relationship,
    "relationship",
    "Vazba",
)
_RESIDENCE = _LinkSpec(
    ResidenceAttachment,
    Residence,
    "residence",
    "Bydliště",
)
_GRAVE_SITE = _LinkSpec(
    GraveSiteAttachment,
    GraveSite,
    "grave_site",
    "Hrobové místo",
)
_PLACE = _LinkSpec(PlaceAttachment, Place, "place", "Místo")


def _raise_service_error(key: str, message: str, code: str) -> NoReturn:
    raise ValidationError({key: ValidationError(message, code=code)})


def _load_current(
    *,
    model: type[models.Model],
    value: models.Model,
    field_name: str,
    label: str,
    allow_archived_id: int | None = None,
) -> models.Model:
    if not isinstance(value, model) or value.pk is None:
        _raise_service_error(
            field_name,
            f"{label} musí být uložený v databázi.",
            f"{field_name}_unsaved",
        )
    try:
        current = model._default_manager.select_for_update().get(pk=value.pk)
    except model.DoesNotExist:
        _raise_service_error(
            field_name,
            f"{label} musí být uložený v databázi.",
            f"{field_name}_unsaved",
        )

    if getattr(current, "deleted_at", None) is not None:
        _raise_service_error(
            field_name,
            f"{label} je měkce odstraněný a nelze jej připojit.",
            f"{field_name}_deleted",
        )
    if (
        getattr(current, "archived_at", None) is not None
        and current.pk != allow_archived_id
    ):
        _raise_service_error(
            field_name,
            f"{label} je archivovaný a nelze jej nově připojit.",
            f"{field_name}_archived",
        )
    return current


def _load_role(
    role: AttachmentRole,
    *,
    allow_inactive_id: int | None = None,
) -> AttachmentRole:
    if not isinstance(role, AttachmentRole) or role.pk is None:
        _raise_service_error(
            "role",
            "Role přílohy musí být uložená v databázi.",
            "role_unsaved",
        )
    try:
        current = AttachmentRole.objects.select_for_update().get(pk=role.pk)
    except AttachmentRole.DoesNotExist:
        _raise_service_error(
            "role",
            "Role přílohy musí být uložená v databázi.",
            "role_unsaved",
        )
    if not current.is_active and current.pk != allow_inactive_id:
        _raise_service_error(
            "role",
            "Neaktivní roli přílohy nelze nově použít.",
            "role_inactive",
        )
    return current


def _load_created_by(
    created_by: AbstractBaseUser | None,
) -> AbstractBaseUser | None:
    if created_by is None:
        return None
    if created_by.pk is None:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "created_by_unsaved",
        )
    user_model = get_user_model()
    try:
        return user_model._default_manager.select_for_update().get(
            pk=created_by.pk
        )
    except user_model.DoesNotExist:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "created_by_unsaved",
        )


def _apply_input(
    link: AttachmentLinkModel,
    *,
    data: AttachmentLinkInput,
    attachment: Attachment,
    role: AttachmentRole,
) -> None:
    link.attachment = attachment
    link.role = role
    link.context_description = data.context_description.strip()
    link.sort_order = data.sort_order
    link.is_primary = data.is_primary
    link.access_level = data.access_level


def _reload(spec: _LinkSpec, link_id: int) -> AttachmentLinkModel:
    return spec.model.objects.select_related(
        spec.target_field,
        "attachment",
        "role",
        "created_by",
    ).get(pk=link_id)


def _save(link: AttachmentLinkModel) -> None:
    link.full_clean()
    try:
        with transaction.atomic():
            link.save()
    except IntegrityError:
        has_primary_conflict = (
            isinstance(link, PersonAttachment)
            and link.is_primary
            and PersonAttachment.objects.filter(
                person_id=link.person_id,
                is_primary=True,
                deleted_at__isnull=True,
            )
            .exclude(pk=link.pk)
            .exists()
        )
        if has_primary_conflict:
            _raise_service_error(
                "is_primary",
                "Osoba už má aktivní primární přílohu.",
                "duplicate_primary_person_attachment",
            )
        raise


def _create_link(
    *,
    spec: _LinkSpec,
    target: models.Model,
    data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None,
) -> AttachmentLinkModel:
    with transaction.atomic():
        current_target = _load_current(
            model=spec.target_model,
            value=target,
            field_name=spec.target_field,
            label=spec.target_label,
        )
        attachment = _load_current(
            model=Attachment,
            value=data.attachment,
            field_name="attachment",
            label="Příloha",
        )
        link = spec.model(
            **{
                spec.target_field: current_target,
                "created_by": _load_created_by(created_by),
            }
        )
        _apply_input(
            link,
            data=data,
            attachment=attachment,
            role=_load_role(data.role),
        )
        _save(link)
        return _reload(spec, link.pk)


def _update_link(
    *,
    spec: _LinkSpec,
    link: AttachmentLinkModel,
    target: models.Model,
    data: AttachmentLinkInput,
) -> AttachmentLinkModel:
    if not isinstance(link, spec.model) or link.pk is None:
        _raise_service_error(
            "link",
            "Vazba přílohy musí být uložená v databázi.",
            "attachment_link_unsaved",
        )
    with transaction.atomic():
        try:
            current_link = spec.model.objects.select_for_update().get(
                pk=link.pk
            )
        except spec.model.DoesNotExist:
            _raise_service_error(
                "link",
                "Vazba přílohy musí být uložená v databázi.",
                "attachment_link_unsaved",
            )
        if current_link.deleted_at is not None:
            _raise_service_error(
                "link",
                "Měkce odstraněnou vazbu přílohy nelze upravit.",
                "attachment_link_deleted",
            )

        current_target_id = getattr(
            current_link,
            f"{spec.target_field}_id",
        )
        current_target = _load_current(
            model=spec.target_model,
            value=target,
            field_name=spec.target_field,
            label=spec.target_label,
            allow_archived_id=current_target_id,
        )
        attachment = _load_current(
            model=Attachment,
            value=data.attachment,
            field_name="attachment",
            label="Příloha",
            allow_archived_id=current_link.attachment_id,
        )
        setattr(current_link, spec.target_field, current_target)
        _apply_input(
            current_link,
            data=data,
            attachment=attachment,
            role=_load_role(
                data.role,
                allow_inactive_id=current_link.role_id,
            ),
        )
        _save(current_link)
        return _reload(spec, current_link.pk)


def create_person_attachment(
    *, person: Person, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> PersonAttachment:
    return _create_link(
        spec=_PERSON, target=person, data=data, created_by=created_by
    )


def update_person_attachment(
    *, link: PersonAttachment, person: Person, data: AttachmentLinkInput,
) -> PersonAttachment:
    return _update_link(spec=_PERSON, link=link, target=person, data=data)


def create_event_attachment(
    *, event: Event, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> EventAttachment:
    return _create_link(
        spec=_EVENT, target=event, data=data, created_by=created_by
    )


def update_event_attachment(
    *, link: EventAttachment, event: Event, data: AttachmentLinkInput,
) -> EventAttachment:
    return _update_link(spec=_EVENT, link=link, target=event, data=data)


def create_relationship_attachment(
    *, relationship: Relationship, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> RelationshipAttachment:
    return _create_link(
        spec=_RELATIONSHIP,
        target=relationship,
        data=data,
        created_by=created_by,
    )


def update_relationship_attachment(
    *, link: RelationshipAttachment, relationship: Relationship,
    data: AttachmentLinkInput,
) -> RelationshipAttachment:
    return _update_link(
        spec=_RELATIONSHIP,
        link=link,
        target=relationship,
        data=data,
    )


def create_residence_attachment(
    *, residence: Residence, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> ResidenceAttachment:
    return _create_link(
        spec=_RESIDENCE,
        target=residence,
        data=data,
        created_by=created_by,
    )


def update_residence_attachment(
    *, link: ResidenceAttachment, residence: Residence,
    data: AttachmentLinkInput,
) -> ResidenceAttachment:
    return _update_link(
        spec=_RESIDENCE,
        link=link,
        target=residence,
        data=data,
    )


def create_grave_site_attachment(
    *, grave_site: GraveSite, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> GraveSiteAttachment:
    return _create_link(
        spec=_GRAVE_SITE,
        target=grave_site,
        data=data,
        created_by=created_by,
    )


def update_grave_site_attachment(
    *, link: GraveSiteAttachment, grave_site: GraveSite,
    data: AttachmentLinkInput,
) -> GraveSiteAttachment:
    return _update_link(
        spec=_GRAVE_SITE,
        link=link,
        target=grave_site,
        data=data,
    )


def create_place_attachment(
    *, place: Place, data: AttachmentLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> PlaceAttachment:
    return _create_link(
        spec=_PLACE, target=place, data=data, created_by=created_by
    )


def update_place_attachment(
    *, link: PlaceAttachment, place: Place, data: AttachmentLinkInput,
) -> PlaceAttachment:
    return _update_link(spec=_PLACE, link=link, target=place, data=data)
