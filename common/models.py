from django.conf import settings
from django.db import models

from .choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)


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


class PartialDateModel(models.Model):
    """Ukládá neúplný nebo nejistý časový údaj bez falešné přesnosti."""

    date_precision = models.CharField(
        max_length=10,
        choices=DatePrecision.choices,
        default=DatePrecision.UNKNOWN,
    )
    date_qualifier = models.CharField(
        max_length=12,
        choices=DateQualifier.choices,
        default=DateQualifier.NONE,
    )

    start_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    start_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    start_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    end_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    end_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    end_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    original_date_text = models.CharField(
        max_length=255,
        blank=True,
    )
    date_note = models.TextField(
        blank=True,
    )

    sort_date = models.DateField(
        null=True,
        blank=True,
        editable=False,
        db_index=True,
    )
    sort_date_end = models.DateField(
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        abstract = True


class LookupModel(models.Model):
    """Společný základ uživatelsky spravovaných číselníků."""

    code = models.CharField(
        max_length=50,
        unique=True,
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.TextField(
        blank=True,
    )
    sort_order = models.PositiveIntegerField(
        default=0,
    )
    is_active = models.BooleanField(
        default=True,
    )
    is_system = models.BooleanField(
        default=False,
        editable=False,
    )

    class Meta:
        abstract = True
        ordering = ("sort_order", "name", "code")
