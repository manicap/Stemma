"""Centralizovaná actor-aware policy zdravotních informací."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db.models import Q

from common.choices import AccessLevel
from common.permissions import can_view_access_level

__all__ = (
    "can_view_health_record_access",
    "get_health_record_visibility_filter",
)

_ALLOWED_HEALTH_ACCESS_LEVELS = (
    AccessLevel.RESTRICTED,
    AccessLevel.ADMIN_ONLY,
)


def can_view_health_record_access(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    access_level: str,
) -> bool:
    """Vyhodnoť health access přes jedinou rozšiřitelnou doménovou hranici."""

    if access_level not in _ALLOWED_HEALTH_ACCESS_LEVELS:
        raise ValidationError(
            {
                "access_level": ValidationError(
                    "Zdravotní záznam nesmí být přístupnější než omezený "
                    "obsah.",
                    code="health_access_too_broad",
                )
            }
        )
    return can_view_access_level(actor=actor, access_level=access_level)


def get_health_record_visibility_filter(
    *,
    actor: AbstractBaseUser | AnonymousUser,
) -> Q:
    """Sestav jediný actor-aware access a lifecycle filtr HealthRecord."""

    visible_health_levels = tuple(
        access_level
        for access_level in _ALLOWED_HEALTH_ACCESS_LEVELS
        if can_view_health_record_access(
            actor=actor,
            access_level=access_level,
        )
    )
    visible_person_levels = tuple(
        access_level
        for access_level in AccessLevel.values
        if can_view_access_level(actor=actor, access_level=access_level)
    )
    return Q(
        access_level__in=visible_health_levels,
        archived_at__isnull=True,
        deleted_at__isnull=True,
        record_type__is_active=True,
        person__access_level__in=visible_person_levels,
        person__archived_at__isnull=True,
        person__deleted_at__isnull=True,
    )
