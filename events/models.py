from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models

from common.choices import AccessLevel, DatePrecision
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from places.models import Place


class EventType(LookupModel):
    """Typ události a jeho výchozí konfigurační hodnoty."""

    supports_date_range = models.BooleanField(
        default=False,
    )
    allows_place = models.BooleanField(
        default=True,
    )
    default_show_in_overview = models.BooleanField(
        default=False,
    )
    default_access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.PUBLIC,
    )

    class Meta(LookupModel.Meta):
        verbose_name = "Typ události"
        verbose_name_plural = "Typy událostí"

    def __str__(self) -> str:
        return self.name


class ParticipantRole(LookupModel):
    """Role osoby v události."""

    class Meta(LookupModel.Meta):
        verbose_name = "Role účastníka"
        verbose_name_plural = "Role účastníků"

    def __str__(self) -> str:
        return self.name


class AllowedEventRole(models.Model):
    """Konfigurace povolené role pro konkrétní typ události."""

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name="allowed_roles",
    )
    participant_role = models.ForeignKey(
        ParticipantRole,
        on_delete=models.PROTECT,
        related_name="event_type_rules",
    )
    min_count = models.PositiveSmallIntegerField(default=0)
    max_count = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(
        default=False,
        editable=False,
    )

    class Meta:
        verbose_name = "Povolená role události"
        verbose_name_plural = "Povolené role událostí"
        ordering = (
            "event_type__sort_order",
            "sort_order",
            "participant_role__sort_order",
            "participant_role__code",
        )
        constraints = (
            models.UniqueConstraint(
                fields=("event_type", "participant_role"),
                name="events_unique_allowed_role",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(max_count__isnull=True)
                    | models.Q(max_count__gte=models.F("min_count"))
                ),
                name="events_valid_allowed_role_counts",
            ),
        )

    def __str__(self) -> str:
        return f"{self.event_type} – {self.participant_role}"


class Event(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    models.Model,
):
    """Obecná historická událost s neúplným časovým údajem."""

    event_type = models.ForeignKey(
        EventType,
        on_delete=models.PROTECT,
        related_name="events",
    )
    place = models.ForeignKey(
        Place,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="events",
    )
    location_detail = models.CharField(
        max_length=255,
        blank=True,
    )
    title = models.CharField(
        max_length=255,
        blank=True,
    )
    description = models.TextField(
        blank=True,
    )
    show_in_overview = models.BooleanField(
        default=False,
    )

    class Meta:
        verbose_name = "Událost"
        verbose_name_plural = "Události"
        ordering = ("sort_date", "sort_date_end", "pk")

    def clean(self) -> None:
        errors: dict[str, list[ValidationError]] = {}

        try:
            super().clean()
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field_name, field_errors in exc.error_dict.items():
                    errors.setdefault(field_name, []).extend(field_errors)
            else:
                errors.setdefault(NON_FIELD_ERRORS, []).extend(
                    exc.error_list
                )

        def add_error(
            field_name: str,
            message: str,
            code: str,
        ) -> None:
            errors.setdefault(field_name, []).append(
                ValidationError(message, code=code)
            )

        try:
            event_type = self.event_type
        except EventType.DoesNotExist:
            event_type = None

        if event_type is not None:
            if (
                not event_type.supports_date_range
                and self.date_precision == DatePrecision.RANGE
            ):
                add_error(
                    "date_precision",
                    "Tento typ události nepodporuje časové rozmezí.",
                    "date_range_not_supported",
                )

            if not event_type.allows_place:
                if self.place_id is not None:
                    add_error(
                        "place",
                        "Tento typ události nepovoluje místo.",
                        "place_not_allowed",
                    )
                if (self.location_detail or "").strip():
                    add_error(
                        "location_detail",
                        "Tento typ události nepovoluje lokalizační detail.",
                        "location_detail_not_allowed",
                    )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        title = (self.title or "").strip()
        if title:
            return title
        try:
            return self.event_type.name
        except EventType.DoesNotExist:
            return "Událost"
