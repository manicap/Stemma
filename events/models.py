from django.db import models

from common.choices import AccessLevel
from common.models import LookupModel


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
