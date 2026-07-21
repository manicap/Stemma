from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models

from common.choices import DatePrecision, Gender
from common.models import (
    AccessControlledModel,
    AuthoredModel,
    LifecycleModel,
    LookupModel,
    PartialDateModel,
    TimestampedModel,
    VerifiableModel,
)

from .choices import RelationshipCategory


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


class RelationshipType(LookupModel):
    """Uživatelsky spravovaný typ vztahu mezi dvěma osobami."""

    forward_label_male = models.CharField(max_length=100)
    forward_label_female = models.CharField(max_length=100)
    forward_label_unknown = models.CharField(max_length=100)

    reverse_label_male = models.CharField(max_length=100)
    reverse_label_female = models.CharField(max_length=100)
    reverse_label_unknown = models.CharField(max_length=100)

    category = models.CharField(
        max_length=20,
        choices=RelationshipCategory.choices,
        default=RelationshipCategory.OTHER,
    )
    is_symmetric = models.BooleanField(default=False)
    supports_date_range = models.BooleanField(default=False)
    is_derivable = models.BooleanField(default=False)

    class Meta(LookupModel.Meta):
        verbose_name = "Typ vazby"
        verbose_name_plural = "Typy vazeb"
        constraints = (
            models.CheckConstraint(
                condition=(
                    models.Q(is_symmetric=False)
                    | (
                        models.Q(
                            forward_label_male=models.F(
                                "reverse_label_male"
                            )
                        )
                        & models.Q(
                            forward_label_female=models.F(
                                "reverse_label_female"
                            )
                        )
                        & models.Q(
                            forward_label_unknown=models.F(
                                "reverse_label_unknown"
                            )
                        )
                    )
                ),
                name="people_symmetric_relationship_labels_match",
            ),
        )

    def clean(self) -> None:
        super().clean()
        if not self.is_symmetric:
            return

        errors = {}
        for forward_field, reverse_field in (
            ("forward_label_male", "reverse_label_male"),
            ("forward_label_female", "reverse_label_female"),
            ("forward_label_unknown", "reverse_label_unknown"),
        ):
            if getattr(self, forward_field) != getattr(self, reverse_field):
                errors[reverse_field] = ValidationError(
                    "U symetrického typu se musí názvy obou směrů shodovat.",
                    code="symmetric_labels_mismatch",
                )

        if errors:
            raise ValidationError(errors)

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


class Relationship(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    models.Model,
):
    """Historická vazba mezi dvěma evidovanými osobami."""

    relationship_type = models.ForeignKey(
        RelationshipType,
        on_delete=models.PROTECT,
        related_name="relationships",
    )
    person_a = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="relationships_as_a",
    )
    person_b = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="relationships_as_b",
    )
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "Vazba"
        verbose_name_plural = "Vazby"
        ordering = (
            "relationship_type__sort_order",
            "sort_date",
            "sort_date_end",
            "person_a_id",
            "person_b_id",
            "pk",
        )
        constraints = (
            models.CheckConstraint(
                condition=~models.Q(person_a=models.F("person_b")),
                name="people_relationship_distinct_persons",
            ),
            models.UniqueConstraint(
                fields=("person_a", "person_b", "relationship_type"),
                condition=models.Q(
                    deleted_at__isnull=True,
                    date_precision=DatePrecision.UNKNOWN,
                ),
                name="people_unique_active_unknown_relationship",
                violation_error_code="duplicate_relationship",
            ),
            models.UniqueConstraint(
                fields=(
                    "person_a",
                    "person_b",
                    "relationship_type",
                    "date_precision",
                    "sort_date",
                    "sort_date_end",
                ),
                condition=(
                    models.Q(deleted_at__isnull=True)
                    & ~models.Q(date_precision=DatePrecision.UNKNOWN)
                ),
                name="people_unique_active_dated_relationship",
                violation_error_code="duplicate_relationship",
            ),
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

        person_a_id = self.person_a_id
        person_b_id = self.person_b_id
        persons_are_available = (
            person_a_id is not None and person_b_id is not None
        )
        relationship_to_self = (
            persons_are_available and person_a_id == person_b_id
        )

        if relationship_to_self:
            add_error(
                "person_b",
                "Vazba nesmí spojovat osobu samu se sebou.",
                "relationship_to_self",
            )

        try:
            relationship_type = self.relationship_type
        except RelationshipType.DoesNotExist:
            relationship_type = None

        if relationship_type is not None:
            if (
                not relationship_type.supports_date_range
                and self.date_precision == DatePrecision.RANGE
            ):
                add_error(
                    "date_precision",
                    "Tento typ vazby nepodporuje časové rozmezí.",
                    "date_range_not_supported",
                )

            if (
                relationship_type.is_symmetric
                and persons_are_available
                and not relationship_to_self
                and person_a_id > person_b_id
            ):
                add_error(
                    "person_b",
                    "Symetrická vazba nemá kanonické pořadí osob.",
                    "symmetric_relationship_not_normalized",
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        try:
            person_a_text = str(self.person_a) or "Neznámá osoba A"
        except Person.DoesNotExist:
            person_a_text = "Neznámá osoba A"

        try:
            relationship_type_text = (
                str(self.relationship_type) or "Vazba"
            )
        except RelationshipType.DoesNotExist:
            relationship_type_text = "Vazba"

        try:
            person_b_text = str(self.person_b) or "Neznámá osoba B"
        except Person.DoesNotExist:
            person_b_text = "Neznámá osoba B"

        return (
            f"{person_a_text} – {relationship_type_text} – "
            f"{person_b_text}"
        )
