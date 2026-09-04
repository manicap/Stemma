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
from health.models import HealthRecord
from people.models import Person, PersonName, Relationship
from places.models import GraveSite, Place, Residence

from .choices import FileStatus, SourceSupport


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


class SourceType(LookupModel):
    """Uživatelsky rozšiřitelná klasifikace informačního pramene."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ zdroje"
        verbose_name_plural = "Typy zdrojů"

    def __str__(self) -> str:
        return self.name


class SourceRole(LookupModel):
    """Význam zdroje vůči konkrétnímu propojenému objektu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Role zdroje"
        verbose_name_plural = "Role zdrojů"

    def __str__(self) -> str:
        return self.name


class Source(
    TimestampedModel,
    PartialDateModel,
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Znovupoužitelný informační pramen s volitelnou bibliografií."""

    source_type = models.ForeignKey(
        SourceType,
        on_delete=models.PROTECT,
        related_name="sources",
    )
    title = models.CharField(max_length=255)
    full_citation = models.TextField(blank=True)
    institution = models.CharField(max_length=255, blank=True)
    fonds = models.CharField(max_length=255, blank=True)
    shelfmark = models.CharField(max_length=255, blank=True)
    volume = models.CharField(max_length=100, blank=True)
    inventory_number = models.CharField(max_length=100, blank=True)
    creator_name = models.CharField(max_length=255, blank=True)
    publication_details = models.TextField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    accessed_on = models.DateField(null=True, blank=True)
    external_identifier = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Zdroj"
        verbose_name_plural = "Zdroje"
        ordering = ("title", "pk")

    def clean(self) -> None:
        super().clean()
        if not (self.title or "").strip():
            raise ValidationError(
                {
                    "title": ValidationError(
                        "Název zdroje nesmí být prázdný.",
                        code="source_title_required",
                    )
                }
            )

    def __str__(self) -> str:
        return (self.title or "").strip() or "Zdroj"


class SourceLinkModel(
    TimestampedModel,
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Společná metadata explicitního propojení zdroje s objektem."""

    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="%(class)s_links",
    )
    role = models.ForeignKey(
        SourceRole,
        on_delete=models.PROTECT,
        related_name="%(class)s_links",
    )
    cited_part = models.CharField(max_length=255, blank=True)
    excerpt = models.TextField(blank=True)
    interpretation = models.TextField(blank=True)
    support_strength = models.CharField(
        max_length=20,
        choices=SourceSupport.choices,
    )

    class Meta:
        abstract = True

    def _link_text(self, target: object) -> str:
        return f"{target} – {self.source}"


class PersonNameSource(SourceLinkModel):
    """Explicitní propojení dalšího jména osoby a zdroje."""

    person_name = models.ForeignKey(
        PersonName,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj jména osoby"
        verbose_name_plural = "Zdroje jmen osob"
        ordering = ("person_name_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.person_name)


class EventSource(SourceLinkModel):
    """Explicitní propojení události a zdroje."""

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj události"
        verbose_name_plural = "Zdroje událostí"
        ordering = ("event_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.event)


class HealthRecordSource(SourceLinkModel):
    """Explicitní propojení zdravotního záznamu a informačního zdroje."""

    health_record = models.ForeignKey(
        HealthRecord,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj zdravotního záznamu"
        verbose_name_plural = "Zdroje zdravotních záznamů"
        ordering = ("health_record_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.health_record)


class RelationshipSource(SourceLinkModel):
    """Explicitní propojení vztahu a zdroje."""

    relationship = models.ForeignKey(
        Relationship,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj vazby"
        verbose_name_plural = "Zdroje vazeb"
        ordering = ("relationship_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.relationship)


class ResidenceSource(SourceLinkModel):
    """Explicitní propojení bydliště a zdroje."""

    residence = models.ForeignKey(
        Residence,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj bydliště"
        verbose_name_plural = "Zdroje bydlišť"
        ordering = ("residence_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.residence)


class GraveSiteSource(SourceLinkModel):
    """Explicitní propojení hrobového místa a zdroje."""

    grave_site = models.ForeignKey(
        GraveSite,
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj hrobového místa"
        verbose_name_plural = "Zdroje hrobových míst"
        ordering = ("grave_site_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.grave_site)


class AttachmentSource(SourceLinkModel):
    """Explicitní propojení digitální přílohy a zdroje."""

    attachment = models.ForeignKey(
        "Attachment",
        on_delete=models.PROTECT,
        related_name="source_links",
    )

    class Meta:
        verbose_name = "Zdroj přílohy"
        verbose_name_plural = "Zdroje příloh"
        ordering = ("attachment_id", "role__sort_order", "pk")

    def __str__(self) -> str:
        return self._link_text(self.attachment)


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


class HealthRecordAttachment(AttachmentLinkModel):
    """Explicitní propojení zdravotního záznamu a jednou uložené přílohy."""

    health_record = models.ForeignKey(
        HealthRecord,
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )
    attachment = models.ForeignKey(
        Attachment,
        on_delete=models.PROTECT,
        related_name="health_record_links",
    )

    class Meta:
        verbose_name = "Příloha zdravotního záznamu"
        verbose_name_plural = "Přílohy zdravotních záznamů"
        ordering = (
            "health_record_id",
            "sort_order",
            "role__sort_order",
            "pk",
        )

    def __str__(self) -> str:
        return self._link_text(self.health_record)


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
