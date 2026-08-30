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
from events.models import Event
from people.models import Person, Relationship
from places.models import GraveSite, Place, Residence

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


class AttachmentLinkModel(
    TimestampedModel,
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Společná metadata explicitního propojení přílohy s objektem."""

    role = models.ForeignKey(
        AttachmentRole,
        on_delete=models.PROTECT,
        related_name="%(class)s_links",
    )
    context_description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def _link_text(self, target: object) -> str:
        return f"{target} – {self.attachment}"


class PersonAttachment(AttachmentLinkModel):
    """Explicitní propojení osoby a jednou uložené přílohy."""

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="person_links",
    )

    class Meta:
        verbose_name = "Příloha osoby"
        verbose_name_plural = "Přílohy osob"
        ordering = ("person_id", "sort_order", "role__sort_order", "pk")
        constraints = (
            models.UniqueConstraint(
                fields=("person",),
                condition=models.Q(
                    is_primary=True,
                    deleted_at__isnull=True,
                ),
                name="materials_unique_active_primary_person_attachment",
                violation_error_code="duplicate_primary_person_attachment",
            ),
        )

    def __str__(self) -> str:
        return self._link_text(self.person)


class EventAttachment(AttachmentLinkModel):
    """Explicitní propojení události a jednou uložené přílohy."""

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="event_links",
    )

    class Meta:
        verbose_name = "Příloha události"
        verbose_name_plural = "Přílohy událostí"
        ordering = ("event_id", "sort_order", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.event)


class RelationshipAttachment(AttachmentLinkModel):
    """Explicitní propojení vztahu a jednou uložené přílohy."""

    relationship = models.ForeignKey(
        Relationship,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="relationship_links",
    )

    class Meta:
        verbose_name = "Příloha vazby"
        verbose_name_plural = "Přílohy vazeb"
        ordering = (
            "relationship_id",
            "sort_order",
            "role__sort_order",
            "pk",
        )

    def __str__(self) -> str:
        return self._link_text(self.relationship)


class ResidenceAttachment(AttachmentLinkModel):
    """Explicitní propojení bydliště a jednou uložené přílohy."""

    residence = models.ForeignKey(
        Residence,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="residence_links",
    )

    class Meta:
        verbose_name = "Příloha bydliště"
        verbose_name_plural = "Přílohy bydlišť"
        ordering = (
            "residence_id",
            "sort_order",
            "role__sort_order",
            "pk",
        )

    def __str__(self) -> str:
        return self._link_text(self.residence)


class GraveSiteAttachment(AttachmentLinkModel):
    """Explicitní propojení hrobového místa a jednou uložené přílohy."""

    grave_site = models.ForeignKey(
        GraveSite,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="grave_site_links",
    )

    class Meta:
        verbose_name = "Příloha hrobového místa"
        verbose_name_plural = "Přílohy hrobových míst"
        ordering = (
            "grave_site_id",
            "sort_order",
            "role__sort_order",
            "pk",
        )

    def __str__(self) -> str:
        return self._link_text(self.grave_site)


class PlaceAttachment(AttachmentLinkModel):
    """Explicitní propojení místa a jednou uložené přílohy."""

    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="place_links",
    )

    class Meta:
        verbose_name = "Příloha místa"
        verbose_name_plural = "Přílohy míst"
        ordering = ("place_id", "sort_order", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.place)
