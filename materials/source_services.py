"""Transakční doménové služby explicitních vazeb zdrojů."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models, transaction

from common.choices import AccessLevel
from events.models import Event
from people.models import PersonName, Relationship
from places.models import GraveSite, Residence

from .choices import SourceSupport
from .models import (
    Attachment,
    AttachmentSource,
    EventSource,
    GraveSiteSource,
    PersonNameSource,
    RelationshipSource,
    ResidenceSource,
    Source,
    SourceLinkModel,
    SourceRole,
)

__all__ = (
    "SourceLinkInput",
    "create_attachment_source",
    "create_event_source",
    "create_grave_site_source",
    "create_person_name_source",
    "create_relationship_source",
    "create_residence_source",
    "update_attachment_source",
    "update_event_source",
    "update_grave_site_source",
    "update_person_name_source",
    "update_relationship_source",
    "update_residence_source",
)


@dataclass(frozen=True, slots=True)
class SourceLinkInput:
    """Úplný snapshot společných editovatelných údajů vazby zdroje."""

    source: Source
    role: SourceRole
    support_strength: str
    cited_part: str = ""
    excerpt: str = ""
    interpretation: str = ""
    access_level: str = AccessLevel.PUBLIC


@dataclass(frozen=True, slots=True)
class _LinkSpec:
    model: type[SourceLinkModel]
    target_model: type[models.Model]
    target_field: str
    target_label: str


_PERSON_NAME = _LinkSpec(PersonNameSource, PersonName, "person_name", "Jméno")
_EVENT = _LinkSpec(EventSource, Event, "event", "Událost")
_RELATIONSHIP = _LinkSpec(
    RelationshipSource, Relationship, "relationship", "Vazba"
)
_RESIDENCE = _LinkSpec(ResidenceSource, Residence, "residence", "Bydliště")
_GRAVE_SITE = _LinkSpec(
    GraveSiteSource, GraveSite, "grave_site", "Hrobové místo"
)
_ATTACHMENT = _LinkSpec(
    AttachmentSource, Attachment, "attachment", "Příloha"
)


def _error(field: str, message: str, code: str) -> NoReturn:
    raise ValidationError({field: ValidationError(message, code=code)})


def _load_current(
    *,
    model: type[models.Model],
    value: models.Model,
    field: str,
    label: str,
    allow_archived_id: int | None = None,
) -> models.Model:
    if not isinstance(value, model) or value.pk is None:
        _error(field, f"{label} musí být uložený v databázi.", f"{field}_unsaved")
    try:
        current = model._default_manager.select_for_update().get(pk=value.pk)
    except model.DoesNotExist:
        _error(field, f"{label} musí být uložený v databázi.", f"{field}_unsaved")
    if current.deleted_at is not None:
        _error(field, f"{label} je měkce odstraněný.", f"{field}_deleted")
    if current.archived_at is not None and current.pk != allow_archived_id:
        _error(field, f"{label} je archivovaný.", f"{field}_archived")
    return current


def _load_role(
    role: SourceRole,
    *,
    allow_inactive_id: int | None = None,
) -> SourceRole:
    if not isinstance(role, SourceRole) or role.pk is None:
        _error("role", "Role zdroje musí být uložená.", "role_unsaved")
    try:
        current = SourceRole.objects.select_for_update().get(pk=role.pk)
    except SourceRole.DoesNotExist:
        _error("role", "Role zdroje musí být uložená.", "role_unsaved")
    if not current.is_active and current.pk != allow_inactive_id:
        _error("role", "Neaktivní roli zdroje nelze nově použít.", "role_inactive")
    return current


def _load_author(
    author: AbstractBaseUser | None,
) -> AbstractBaseUser | None:
    if author is None:
        return None
    if author.pk is None:
        _error("created_by", "Autor musí být uložený.", "created_by_unsaved")
    user_model = get_user_model()
    try:
        return user_model._default_manager.select_for_update().get(pk=author.pk)
    except user_model.DoesNotExist:
        _error("created_by", "Autor musí být uložený.", "created_by_unsaved")


def _apply(
    link: SourceLinkModel,
    *,
    data: SourceLinkInput,
    source: Source,
    role: SourceRole,
) -> None:
    link.source = source
    link.role = role
    link.support_strength = data.support_strength
    link.cited_part = data.cited_part.strip()
    link.excerpt = data.excerpt.strip()
    link.interpretation = data.interpretation.strip()
    link.access_level = data.access_level


def _reload(spec: _LinkSpec, link_id: int) -> SourceLinkModel:
    return spec.model.objects.select_related(
        spec.target_field,
        "source",
        "source__source_type",
        "role",
        "created_by",
    ).get(pk=link_id)


def _create(
    *,
    spec: _LinkSpec,
    target: models.Model,
    data: SourceLinkInput,
    created_by: AbstractBaseUser | None,
) -> SourceLinkModel:
    with transaction.atomic():
        current_target = _load_current(
            model=spec.target_model,
            value=target,
            field=spec.target_field,
            label=spec.target_label,
        )
        source = _load_current(
            model=Source,
            value=data.source,
            field="source",
            label="Zdroj",
        )
        link = spec.model(
            **{
                spec.target_field: current_target,
                "created_by": _load_author(created_by),
            }
        )
        _apply(link, data=data, source=source, role=_load_role(data.role))
        link.full_clean()
        link.save()
        return _reload(spec, link.pk)


def _update(
    *,
    spec: _LinkSpec,
    link: SourceLinkModel,
    target: models.Model,
    data: SourceLinkInput,
) -> SourceLinkModel:
    if not isinstance(link, spec.model) or link.pk is None:
        _error("link", "Vazba zdroje musí být uložená.", "source_link_unsaved")
    with transaction.atomic():
        try:
            current = spec.model.objects.select_for_update().get(pk=link.pk)
        except spec.model.DoesNotExist:
            _error("link", "Vazba zdroje musí být uložená.", "source_link_unsaved")
        if current.deleted_at is not None:
            _error(
                "link",
                "Měkce odstraněnou vazbu nelze upravit.",
                "source_link_deleted",
            )
        current_target = _load_current(
            model=spec.target_model,
            value=target,
            field=spec.target_field,
            label=spec.target_label,
            allow_archived_id=getattr(current, f"{spec.target_field}_id"),
        )
        source = _load_current(
            model=Source,
            value=data.source,
            field="source",
            label="Zdroj",
            allow_archived_id=current.source_id,
        )
        setattr(current, spec.target_field, current_target)
        _apply(
            current,
            data=data,
            source=source,
            role=_load_role(data.role, allow_inactive_id=current.role_id),
        )
        current.full_clean()
        current.save()
        return _reload(spec, current.pk)


def create_person_name_source(
    *, person_name: PersonName, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> PersonNameSource:
    return _create(
        spec=_PERSON_NAME,
        target=person_name,
        data=data,
        created_by=created_by,
    )


def update_person_name_source(
    *, link: PersonNameSource, person_name: PersonName, data: SourceLinkInput,
) -> PersonNameSource:
    return _update(spec=_PERSON_NAME, link=link, target=person_name, data=data)


def create_event_source(
    *, event: Event, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> EventSource:
    return _create(spec=_EVENT, target=event, data=data, created_by=created_by)


def update_event_source(
    *, link: EventSource, event: Event, data: SourceLinkInput,
) -> EventSource:
    return _update(spec=_EVENT, link=link, target=event, data=data)


def create_relationship_source(
    *, relationship: Relationship, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> RelationshipSource:
    return _create(
        spec=_RELATIONSHIP,
        target=relationship,
        data=data,
        created_by=created_by,
    )


def update_relationship_source(
    *, link: RelationshipSource, relationship: Relationship,
    data: SourceLinkInput,
) -> RelationshipSource:
    return _update(
        spec=_RELATIONSHIP,
        link=link,
        target=relationship,
        data=data,
    )


def create_residence_source(
    *, residence: Residence, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> ResidenceSource:
    return _create(
        spec=_RESIDENCE,
        target=residence,
        data=data,
        created_by=created_by,
    )


def update_residence_source(
    *, link: ResidenceSource, residence: Residence, data: SourceLinkInput,
) -> ResidenceSource:
    return _update(spec=_RESIDENCE, link=link, target=residence, data=data)


def create_grave_site_source(
    *, grave_site: GraveSite, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> GraveSiteSource:
    return _create(
        spec=_GRAVE_SITE,
        target=grave_site,
        data=data,
        created_by=created_by,
    )


def update_grave_site_source(
    *, link: GraveSiteSource, grave_site: GraveSite,
    data: SourceLinkInput,
) -> GraveSiteSource:
    return _update(
        spec=_GRAVE_SITE,
        link=link,
        target=grave_site,
        data=data,
    )


def create_attachment_source(
    *, attachment: Attachment, data: SourceLinkInput,
    created_by: AbstractBaseUser | None = None,
) -> AttachmentSource:
    return _create(
        spec=_ATTACHMENT,
        target=attachment,
        data=data,
        created_by=created_by,
    )


def update_attachment_source(
    *, link: AttachmentSource, attachment: Attachment,
    data: SourceLinkInput,
) -> AttachmentSource:
    return _update(
        spec=_ATTACHMENT,
        link=link,
        target=attachment,
        data=data,
    )
