from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models

from common.choices import AccessLevel
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
from places.models import Place


class HealthRecordType(LookupModel):
    """Uživatelsky rozšiřitelná klasifikace zdravotního záznamu."""

    class Meta(LookupModel.Meta):
        verbose_name = "Typ zdravotního záznamu"
        verbose_name_plural = "Typy zdravotních záznamů"

    def __str__(self) -> str:
        return self.name


class HealthRecord(
    TimestampedModel,
    AccessControlledModel,
    VerifiableModel,
    AuthoredModel,
    LifecycleModel,
    PartialDateModel,
    models.Model,
):
    """Citlivá zdravotní informace patřící jedné osobě."""

    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="health_records",
    )
    record_type = models.ForeignKey(
        HealthRecordType,
        on_delete=models.PROTECT,
        related_name="health_records",
    )
    place = models.ForeignKey(
        Place,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="health_records",
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    provider_name = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)
    access_level = models.CharField(
        max_length=20,
        choices=AccessLevel.choices,
        default=AccessLevel.RESTRICTED,
    )

    class Meta:
        verbose_name = "Zdravotní záznam"
        verbose_name_plural = "Zdravotní záznamy"
        ordering = ("person_id", "sort_date", "sort_date_end", "pk")
        constraints = (
            models.CheckConstraint(
                condition=models.Q(
                    access_level__in=(
                        AccessLevel.RESTRICTED,
                        AccessLevel.ADMIN_ONLY,
                    )
                ),
                name="health_record_access_not_broader_than_restricted",
                violation_error_code="health_access_too_broad",
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
                errors.setdefault(NON_FIELD_ERRORS, []).extend(exc.error_list)

        if not (self.title or "").strip() and not (
            self.description or ""
        ).strip():
            errors.setdefault(NON_FIELD_ERRORS, []).append(
                ValidationError(
                    "Zdravotní záznam musí mít název nebo popis.",
                    code="health_record_content_required",
                )
            )
        if self.access_level not in (
            AccessLevel.RESTRICTED,
            AccessLevel.ADMIN_ONLY,
        ):
            errors.setdefault("access_level", []).append(
                ValidationError(
                    "Zdravotní záznam nesmí být přístupnější než omezený "
                    "obsah.",
                    code="health_access_too_broad",
                )
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        title = (self.title or "").strip()
        if title:
            return title
        description = (self.description or "").strip()
        return description or "Zdravotní záznam"
