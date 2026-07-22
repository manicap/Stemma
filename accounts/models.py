"""User models for the Stemma application."""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model for Stemma."""

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
