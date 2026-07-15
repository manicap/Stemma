from django.db import models

from .choices import AccessLevel, VerificationStatus


class TimestampedModel(models.Model):
    """Přidává čas vytvoření a poslední změny záznamu."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
