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
