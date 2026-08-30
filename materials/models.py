from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
)

from .choices import FileStatus


class AttachmentCategory(LookupModel):
    """Uživatelsky rozšiřitelná kategorie digitální přílohy."""

    class Meta(LookupModel.Meta):
        verbose_name = "Kategorie přílohy"
        verbose_name_plural = "Kategorie příloh"

    def __str__(self) -> str:
        return self.name


class AttachmentRole(LookupModel):
    """Význam explicitního propojení přílohy s doménovým objektem."""

    class Meta(LookupModel.Meta):
        verbose_name = "Role přílohy"
        verbose_name_plural = "Role příloh"

    def __str__(self) -> str:
        return self.name


class Attachment(
    TimestampedModel,
    PartialDateModel,
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Metadata jednoho fyzického digitálního souboru."""

    category = models.ForeignKey(
        AttachmentCategory,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    display_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    original_filename = models.CharField(max_length=255)
    storage_key = models.CharField(max_length=500, unique=True)
    mime_type = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(
        max_length=64,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9a-f]{64}$",
                message=(
                    "Kontrolní součet musí být SHA-256 zapsaný "
                    "64 malými hexadecimálními znaky."
                ),
                code="invalid_sha256",
            )
        ],
    )
    file_status = models.CharField(
        max_length=20,
        choices=FileStatus.choices,
        default=FileStatus.PENDING,
        db_index=True,
    )
    creator_name = models.CharField(max_length=255, blank=True)
    provenance = models.TextField(blank=True)
    original_owner = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=35, blank=True)
    technical_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Příloha"
        verbose_name_plural = "Přílohy"

    def clean(self) -> None:
        super().clean()
        if not isinstance(self.technical_metadata, dict):
            raise ValidationError(
                {
                    "technical_metadata": ValidationError(
                        "Technická metadata musí být JSON objekt.",
                        code="technical_metadata_not_object",
                    )
                }
            )

    def __str__(self) -> str:
        return (
            self.display_name.strip()
            or self.original_filename.strip()
            or self.storage_key
        )
