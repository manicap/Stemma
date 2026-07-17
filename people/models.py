from django.core.exceptions import ValidationError
from django.db import models

from common.choices import Gender
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)


class PersonCategory(LookupModel):
    """Kategorie obecného zařazení osoby v rodinném příběhu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Kategorie osoby"
        verbose_name_plural = "Kategorie osob"

    def __str__(self) -> str:
        return self.name


class NameType(LookupModel):
    """Typ historického nebo alternativního jména osoby."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ jména"
        verbose_name_plural = "Typy jmen"

    def __str__(self) -> str:
        return self.name


class Person(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    models.Model,
):
    """Stabilní identita osoby bez odvozených životních údajů."""

    category = models.ForeignKey(
        PersonCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="persons",
    )
    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
    )
    notes = models.TextField(
        blank=True,
    )

    class Meta:
        verbose_name = "Osoba"
        verbose_name_plural = "Osoby"
        ordering = ("last_name", "first_name")

    def clean(self) -> None:
        super().clean()
        first_name = (self.first_name or "").strip()
        last_name = (self.last_name or "").strip()
        if not first_name and not last_name:
            raise ValidationError(
                "Musí být vyplněno alespoň jméno nebo příjmení."
            )

    def __str__(self) -> str:
        return " ".join(
            part for part in (self.last_name, self.first_name) if part
        )


class PersonName(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    models.Model,
):
    """Historické nebo alternativní jméno evidované osoby."""

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="names",
    )
    name_type = models.ForeignKey(
        NameType,
        on_delete=models.PROTECT,
        related_name="person_names",
    )
    value = models.CharField(
        max_length=255,
    )
    normalized_value = models.CharField(
        max_length=255,
        db_index=True,
    )
    note = models.TextField(
        blank=True,
    )

    class Meta:
        verbose_name = "Jméno osoby"
        verbose_name_plural = "Jména osob"
        ordering = ("name_type__sort_order", "value")

    def __str__(self) -> str:
        if not self.name_type_id:
            return self.value
        try:
            type_name = self.name_type.name
        except NameType.DoesNotExist:
            return self.value
        if type_name:
            return f"{self.value} ({type_name})"
        return self.value
