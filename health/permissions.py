"""Centralizovaná actor-aware policy zdravotních informací."""

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from common.choices import AccessLevel
from common.permissions import can_view_access_level

__all__ = ("can_view_health_record_access",)

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
