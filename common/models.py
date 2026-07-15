from django.conf import settings
from django.db import models

from .choices import AccessLevel, VerificationStatus


class TimestampedModel(models.Model):
    """Přidává čas vytvoření a poslední změny záznamu."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuthoredModel(models.Model):
    """Eviduje uživatele, který záznam vytvořil."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        abstract = True


class AccessControlledModel(models.Model):
    """Přidává záznamu přístupovou úroveň."""

    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
    )

    class Meta:
        abstract = True


class VerifiableModel(models.Model):
    """Přidává záznamu stav ověření."""

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNCONFIRMED,
    )

    class Meta:
        abstract = True


class LifecycleModel(models.Model):
    """Rozlišuje archivaci záznamu a jeho měkké odstranění."""

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    archive_reason = models.TextField(blank=True)

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    deletion_reason = models.TextField(blank=True)

    class Meta:
        abstract = True
