from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models

from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)
from people.models import Person

from .choices import GraveSiteStatus


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


class GraveSiteType(LookupModel):
    """Druh hrobového, pohřebního nebo pamětního místa."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ hrobového místa"
        verbose_name_plural = "Typy hrobových míst"

    def __str__(self) -> str:
        return self.name


class PersonGraveSiteRole(LookupModel):
    """Význam propojení osoby s hrobovým nebo pamětním místem."""

    class Meta(LookupModel.Meta):
        verbose_name = "Role osoby u hrobového místa"
        verbose_name_plural = "Role osob u hrobových míst"

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


class GraveSite(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Jedno konkrétní hrobové, pohřební nebo pamětní místo."""

    grave_site_type = models.ForeignKey(
        GraveSiteType,
        on_delete=models.PROTECT,
        related_name="grave_sites",
    )
    status = models.CharField(
        max_length=20,
        choices=GraveSiteStatus.choices,
        default=GraveSiteStatus.UNKNOWN,
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="grave_sites",
        null=True,
        blank=True,
    )
    location_text = models.CharField(
        max_length=500,
        blank=True,
    )
    cemetery_name = models.CharField(
        max_length=255,
        blank=True,
    )
    section = models.CharField(
        max_length=100,
        blank=True,
    )
    row = models.CharField(
        max_length=100,
        blank=True,
    )
    grave_number = models.CharField(
        max_length=100,
        blank=True,
    )
    inscription = models.TextField(
        blank=True,
    )
    latitude = models.DecimalField(
        max_digits=9,
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
    note = models.TextField(
        blank=True,
    )

    class Meta:
        verbose_name = "Hrobové nebo pamětní místo"
        verbose_name_plural = "Hrobová a pamětní místa"
        ordering = (
            "cemetery_name",
            "section",
            "row",
            "grave_number",
            "pk",
        )

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

        has_latitude = self.latitude is not None
        has_longitude = self.longitude is not None
        has_coordinates = has_latitude and has_longitude
        has_text_location = any(
            (value or "").strip()
            for value in (self.location_text, self.cemetery_name)
        )

        if (
            self.place_id is None
            and not has_text_location
            and not has_coordinates
        ):
            add_error(
                "location_text",
                "Hrobové nebo pamětní místo musí mít uvedenou lokalitu.",
                "grave_site_location_required",
            )

        if has_latitude != has_longitude:
            missing_field = "longitude" if has_latitude else "latitude"
            add_error(
                missing_field,
                "Zeměpisná šířka a délka musí být zadány společně.",
                "grave_site_coordinates_incomplete",
            )

        if has_latitude and not -90 <= self.latitude <= 90:
            add_error(
                "latitude",
                "Zeměpisná šířka musí být v rozsahu -90 až 90.",
                "grave_site_latitude_out_of_range",
            )

        if has_longitude and not -180 <= self.longitude <= 180:
            add_error(
                "longitude",
                "Zeměpisná délka musí být v rozsahu -180 až 180.",
                "grave_site_longitude_out_of_range",
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        location = (self.cemetery_name or "").strip()
        if not location:
            location = (self.location_text or "").strip()
        if not location:
            try:
                location = (
                    str(self.place).strip()
                    if self.place is not None
                    else ""
                )
            except Place.DoesNotExist:
                location = ""
        if (
            not location
            and self.latitude is not None
            and self.longitude is not None
        ):
            location = f"{self.latitude}, {self.longitude}"
        if not location:
            location = "Hrobové nebo pamětní místo"

        identifiers = []
        for label, value in (
            ("oddíl", self.section),
            ("řada", self.row),
            ("hrob", self.grave_number),
        ):
            clean_value = (value or "").strip()
            if clean_value:
                identifiers.append(f"{label} {clean_value}")
        if identifiers:
            location = f"{location} – {', '.join(identifiers)}"

        try:
            grave_site_type = str(self.grave_site_type).strip()
        except GraveSiteType.DoesNotExist:
            grave_site_type = ""
        if grave_site_type:
            return f"{location} – {grave_site_type}"
        return location


class PersonGraveSite(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Jedno tvrzení o propojení osoby s hrobovým místem v dané roli."""

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="grave_site_links",
    )
    grave_site = models.ForeignKey(
        GraveSite,
        on_delete=models.PROTECT,
        related_name="person_links",
    )
    role = models.ForeignKey(
        PersonGraveSiteRole,
        on_delete=models.PROTECT,
        related_name="person_grave_site_links",
    )
    note = models.TextField(
        blank=True,
    )

    class Meta:
        verbose_name = "Propojení osoby s hrobovým místem"
        verbose_name_plural = "Propojení osob s hrobovými místy"
        ordering = (
            "person_id",
            "grave_site_id",
            "role__sort_order",
            "role__name",
            "pk",
        )

    def __str__(self) -> str:
        try:
            person_text = str(self.person).strip() or "Neznámá osoba"
        except Person.DoesNotExist:
            person_text = "Neznámá osoba"

        try:
            role_text = str(self.role).strip() or "Neznámá role"
        except PersonGraveSiteRole.DoesNotExist:
            role_text = "Neznámá role"

        try:
            grave_site_text = (
                str(self.grave_site).strip() or "Hrobové místo"
            )
        except GraveSite.DoesNotExist:
            grave_site_text = "Hrobové místo"

        return f"{person_text} – {role_text} – {grave_site_text}"


class Residence(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    models.Model,
):
    """Jeden souvislý pobyt evidované osoby."""

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="residences",
    )
    residence_type = models.ForeignKey(
        ResidenceType,
        on_delete=models.PROTECT,
        related_name="residences",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="residences",
        null=True,
        blank=True,
    )
    address_text = models.CharField(
        max_length=500,
        blank=True,
    )
    note = models.TextField(
        blank=True,
    )

    class Meta:
        verbose_name = "Bydliště"
        verbose_name_plural = "Bydliště"
        ordering = (
            "person_id",
            "sort_date",
            "sort_date_end",
            "residence_type__sort_order",
            "pk",
        )

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

        if self.place_id is None and not (
            self.address_text or ""
        ).strip():
            errors.setdefault("address_text", []).append(
                ValidationError(
                    "Bydliště musí mít vybrané místo nebo uvedenou "
                    "adresu či lokalitu.",
                    code="residence_location_required",
                )
            )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        try:
            person_text = str(self.person) or "Neznámá osoba"
        except Person.DoesNotExist:
            person_text = "Neznámá osoba"

        try:
            residence_type_text = (
                str(self.residence_type) or "Typ bydliště"
            )
        except ResidenceType.DoesNotExist:
            residence_type_text = "Typ bydliště"

        location_parts: list[str] = []
        try:
            place_text = str(self.place) if self.place is not None else ""
        except Place.DoesNotExist:
            place_text = ""
        if place_text:
            location_parts.append(place_text)
        if self.address_text:
            location_parts.append(self.address_text)
        location_text = ", ".join(location_parts) or "Neznámá lokalita"

        return (
            f"{person_text} – {residence_type_text} – {location_text}"
        )
