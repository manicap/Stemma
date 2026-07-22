"""Obecná pravidla viditelnosti podle přístupové úrovně."""

from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from .choices import AccessLevel

__all__ = ("can_view_access_level",)

_REQUIRED_ACTOR_ATTRIBUTES = (
    "has_perm",
    "is_active",
    "is_authenticated",
    "is_superuser",
    "pk",
)
_ACCESS_LEVEL_PERMISSIONS = {
    AccessLevel.RESTRICTED: "accounts.view_restricted_content",
    AccessLevel.ADMIN_ONLY: "accounts.view_admin_only_content",
}


def _raise_permission_error(
    key: str,
    message: str,
    code: str,
) -> NoReturn:
    raise ValidationError(
        {key: ValidationError(message, code=code)}
    )


def _load_current_actor(
    actor: AbstractBaseUser,
) -> AbstractBaseUser:
    if actor.pk is None:
        _raise_permission_error(
            "actor",
            "Přihlášený uživatel musí být uložený a existovat v databázi.",
            "actor_unsaved",
        )

    user_model = get_user_model()
    try:
        return user_model._default_manager.get(pk=actor.pk)
    except user_model.DoesNotExist:
        _raise_permission_error(
            "actor",
            "Přihlášený uživatel musí být uložený a existovat v databázi.",
            "actor_unsaved",
        )


def can_view_access_level(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    access_level: str,
) -> bool:
    """Rozhodni viditelnost úrovně podle aktuálního stavu actora."""

    if access_level not in AccessLevel.values:
        _raise_permission_error(
            "access_level",
            "Neznámá úroveň přístupu.",
            "invalid_access_level",
        )

    if (
        actor is None
        or any(
            not hasattr(actor, attribute)
            for attribute in _REQUIRED_ACTOR_ATTRIBUTES
        )
        or not callable(actor.has_perm)
    ):
        _raise_permission_error(
            "actor",
            "Actor není platným uživatelem ani anonymním návštěvníkem.",
            "actor_invalid",
        )

    if not actor.is_authenticated:
        return access_level == AccessLevel.PUBLIC

    current_actor = _load_current_actor(actor)
    if not current_actor.is_active:
        return access_level == AccessLevel.PUBLIC
    if access_level in (
        AccessLevel.PUBLIC,
        AccessLevel.AUTHENTICATED,
    ):
        return True
    if current_actor.is_superuser:
        return True

    return current_actor.has_perm(
        _ACCESS_LEVEL_PERMISSIONS[access_level]
    )
