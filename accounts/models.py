"""User models for the Stemma application."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import transaction


class StemmaUserManager(UserManager):
    """Create the user's owned attachment Vault at the account boundary."""

    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        with transaction.atomic(using=self._db):
            user = super()._create_user(
                username,
                email,
                password,
                **extra_fields,
            )
            from materials.services import get_or_create_owned_vault

            get_or_create_owned_vault(owner=user)
            return user


class User(AbstractUser):
    """Custom user model for Stemma."""

    objects = StemmaUserManager()

    class Meta(AbstractUser.Meta):
        permissions = (
            (
                "view_restricted_content",
                "Může zobrazit omezený obsah",
            ),
            (
                "view_admin_only_content",
                "Může zobrazit obsah pouze pro správce",
            ),
        )
