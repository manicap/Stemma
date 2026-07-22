from django.core.exceptions import ValidationError
from django.db import models

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    TimestampedModel,
    VerifiableModel,
)


class PlaceType(LookupModel):
    """Typ geografického nebo fyzického místa."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ místa"
        verbose_name_plural = "Typy míst"

    def __str__(self) -> str:
        return self.name


class ResidenceType(LookupModel):
    """Druh faktického nebo evidovaného bydliště či pobytu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ bydliště"
        verbose_name_plural = "Typy bydliště"

    def __str__(self) -> str:
        return self.name


class Place(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Opakovaně použitelné geografické nebo fyzické místo."""

    place_type = models.ForeignKey(
        PlaceType,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="places",
    )
    name = models.CharField(
        max_length=255,
    )
    normalized_name = models.CharField(
        max_length=255,
        db_index=True,
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    country = models.CharField(
        max_length=100,
        blank=True,
    )
    description = models.TextField(
        blank=True,
    )
    latitude = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    coordinate_precision_m = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Místo"
        verbose_name_plural = "Místa"
        ordering = ("name",)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, list[ValidationError]] = {}

        def add_error(
            field_name: str,
            message: str,
            code: str,
        ) -> None:
            errors.setdefault(field_name, []).append(
                ValidationError(message, code=code)
            )

        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None

        if has_latitude != has_longitude:
            missing_field = "longitude" if has_latitude else "latitude"
            add_error(
                missing_field,
                "Zeměpisná šířka a délka musí být zadány společně.",
                "coordinates_incomplete",
            )

        if has_latitude and not -90 <= self.latitude <= 90:
            add_error(
                "latitude",
                "Zeměpisná šířka musí být v rozsahu -90 až 90.",
                "latitude_out_of_range",
            )

        if has_longitude and not -180 <= self.longitude <= 180:
            add_error(
                "longitude",
                "Zeměpisná délka musí být v rozsahu -180 až 180.",
                "longitude_out_of_range",
            )

        if self.coordinate_precision_m is not None and not (
            has_latitude and has_longitude
        ):
            add_error(
                "coordinate_precision_m",
                "Přesnost lze zadat pouze společně se souřadnicemi.",
                "precision_without_coordinates",
            )

        if self.parent_id is not None:
            if self.pk is not None and self.parent_id == self.pk:
                add_error(
                    "parent",
                    "Místo nemůže být samo sobě rodičem.",
                    "parent_self",
                )
            else:
                ancestor_id = self.parent_id
                visited_ids: set[int] = set()
                while ancestor_id is not None:
                    if self.pk is not None and ancestor_id == self.pk:
                        add_error(
                            "parent",
                            "Hierarchie míst nesmí obsahovat cyklus.",
                            "parent_cycle",
                        )
                        break
                    if ancestor_id in visited_ids:
                        add_error(
                            "parent",
                            "Hierarchie míst nesmí obsahovat cyklus.",
                            "parent_cycle",
                        )
                        break
                    visited_ids.add(ancestor_id)
                    ancestor_id = (
                        type(self)
                        .objects.filter(pk=ancestor_id)
                        .values_list("parent_id", flat=True)
                        .first()
                    )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return self.name
