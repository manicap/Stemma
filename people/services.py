"""Doménové služby aplikace people."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)

from .models import Person, Relationship, RelationshipType

__all__ = (
    "RelationshipInput",
    "create_relationship",
    "update_relationship",
)


@dataclass(frozen=True, slots=True)
class RelationshipInput:
    """Hodnoty pro vytvoření nebo změnu vazby mezi osobami."""

    relationship_type: RelationshipType
    person_a: Person
    person_b: Person

    note: str = ""

    access_level: str = AccessLevel.PUBLIC
    verification_status: str = VerificationStatus.UNCONFIRMED

    date_precision: str = DatePrecision.UNKNOWN
    date_qualifier: str = DateQualifier.NONE

    start_year: int | None = None
    start_month: int | None = None
    start_day: int | None = None

    end_year: int | None = None
    end_month: int | None = None
    end_day: int | None = None

    original_date_text: str = ""
    date_note: str = ""


def _raise_service_error(key: str, message: str, code: str) -> NoReturn:
    raise ValidationError(
        {key: ValidationError(message, code=code)}
    )


def _load_relationship_type(
    relationship_type: RelationshipType,
) -> RelationshipType:
    if relationship_type.pk is None:
        _raise_service_error(
            "relationship_type",
            "Typ vazby musí být uložený v databázi.",
            "relationship_type_unsaved",
        )

    try:
        return RelationshipType.objects.select_for_update().get(
            pk=relationship_type.pk
        )
    except RelationshipType.DoesNotExist:
        _raise_service_error(
            "relationship_type",
            "Typ vazby musí být uložený v databázi.",
            "relationship_type_unsaved",
        )


def _load_person(
    person: Person,
    *,
    key: str,
    code: str,
) -> Person:
    if person.pk is None:
        _raise_service_error(
            key,
            "Osoba musí být uložená v databázi.",
            code,
        )

    try:
        return Person.objects.select_for_update().get(pk=person.pk)
    except Person.DoesNotExist:
        _raise_service_error(
            key,
            "Osoba musí být uložená v databázi.",
            code,
        )


def _load_created_by(
    created_by: AbstractBaseUser | None,
) -> AbstractBaseUser | None:
    if created_by is None:
        return None
    if created_by.pk is None:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "relationship_created_by_unsaved",
        )

    user_model = get_user_model()
    try:
        return user_model._default_manager.select_for_update().get(
            pk=created_by.pk
        )
    except user_model.DoesNotExist:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "relationship_created_by_unsaved",
        )


def _normalize_people(
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
) -> tuple[Person, Person]:
    if (
        relationship_type.is_symmetric
        and person_a.pk != person_b.pk
        and person_a.pk > person_b.pk
    ):
        return person_b, person_a
    return person_a, person_b


def _apply_input(
    relationship: Relationship,
    *,
    data: RelationshipInput,
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
) -> None:
    relationship.relationship_type = relationship_type
    relationship.person_a = person_a
    relationship.person_b = person_b
    relationship.note = data.note
    relationship.access_level = data.access_level
    relationship.verification_status = data.verification_status
    relationship.date_precision = data.date_precision
    relationship.date_qualifier = data.date_qualifier
    relationship.start_year = data.start_year
    relationship.start_month = data.start_month
    relationship.start_day = data.start_day
    relationship.end_year = data.end_year
    relationship.end_month = data.end_month
    relationship.end_day = data.end_day
    relationship.original_date_text = data.original_date_text
    relationship.date_note = data.date_note


def _reload_relationship(relationship_id: int) -> Relationship:
    return Relationship.objects.select_related(
        "relationship_type",
        "person_a",
        "person_b",
        "created_by",
    ).get(pk=relationship_id)


def _has_duplicate_relationship(
    relationship: Relationship,
    *,
    exclude_pk: int | None,
) -> bool:
    filters: dict[str, object] = {
        "relationship_type_id": relationship.relationship_type_id,
        "person_a_id": relationship.person_a_id,
        "person_b_id": relationship.person_b_id,
        "deleted_at__isnull": True,
        "date_precision": relationship.date_precision,
    }
    if relationship.date_precision != DatePrecision.UNKNOWN:
        filters.update(
            sort_date=relationship.sort_date,
            sort_date_end=relationship.sort_date_end,
        )

    queryset = Relationship.objects.filter(**filters)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.exists()


def _raise_duplicate_relationship() -> NoReturn:
    _raise_service_error(
        NON_FIELD_ERRORS,
        "Stejná vazba se stejným časovým vymezením již existuje.",
        "duplicate_relationship",
    )


def create_relationship(
    *,
    data: RelationshipInput,
    created_by: AbstractBaseUser | None = None,
) -> Relationship:
    """Atomicky vytvoř a vrať čerstvě načtenou vazbu."""

    candidate: Relationship | None = None
    try:
        with transaction.atomic():
            relationship_type = _load_relationship_type(
                data.relationship_type
            )
            person_a = _load_person(
                data.person_a,
                key="person_a",
                code="relationship_person_a_unsaved",
            )
            person_b = _load_person(
                data.person_b,
                key="person_b",
                code="relationship_person_b_unsaved",
            )
            current_created_by = _load_created_by(created_by)

            if not relationship_type.is_active:
                _raise_service_error(
                    "relationship_type",
                    "Neaktivní typ vazby nelze použít pro nový vztah.",
                    "relationship_type_inactive",
                )

            person_a, person_b = _normalize_people(
                relationship_type,
                person_a,
                person_b,
            )
            candidate = Relationship(created_by=current_created_by)
            _apply_input(
                candidate,
                data=data,
                relationship_type=relationship_type,
                person_a=person_a,
                person_b=person_b,
            )
            candidate.full_clean()
            candidate.save()
            return _reload_relationship(candidate.pk)
    except IntegrityError:
        if candidate is not None and _has_duplicate_relationship(
            candidate,
            exclude_pk=None,
        ):
            _raise_duplicate_relationship()
        raise


def update_relationship(
    *,
    relationship: Relationship,
    data: RelationshipInput,
) -> Relationship:
    """Atomicky změň a vrať čerstvě načtenou vazbu."""

    if relationship.pk is None:
        _raise_service_error(
            "relationship",
            "Vazba musí být uložená v databázi.",
            "relationship_unsaved",
        )

    candidate: Relationship | None = None
    relationship_id = relationship.pk
    try:
        with transaction.atomic():
            try:
                candidate = Relationship.objects.select_for_update().get(
                    pk=relationship_id
                )
            except Relationship.DoesNotExist:
                _raise_service_error(
                    "relationship",
                    "Vazba musí být uložená v databázi.",
                    "relationship_unsaved",
                )

            if candidate.deleted_at is not None:
                _raise_service_error(
                    "relationship",
                    "Měkce odstraněnou vazbu nelze upravit.",
                    "relationship_deleted",
                )

            original_relationship_type_id = candidate.relationship_type_id
            relationship_type = _load_relationship_type(
                data.relationship_type
            )
            person_a = _load_person(
                data.person_a,
                key="person_a",
                code="relationship_person_a_unsaved",
            )
            person_b = _load_person(
                data.person_b,
                key="person_b",
                code="relationship_person_b_unsaved",
            )

            if (
                not relationship_type.is_active
                and relationship_type.pk != original_relationship_type_id
            ):
                _raise_service_error(
                    "relationship_type",
                    "Na jiný neaktivní typ vazby nelze přejít.",
                    "relationship_type_inactive",
                )

            person_a, person_b = _normalize_people(
                relationship_type,
                person_a,
                person_b,
            )
            _apply_input(
                candidate,
                data=data,
                relationship_type=relationship_type,
                person_a=person_a,
                person_b=person_b,
            )
            candidate.full_clean()
            candidate.save()
            return _reload_relationship(candidate.pk)
    except IntegrityError:
        if candidate is not None and _has_duplicate_relationship(
            candidate,
            exclude_pk=relationship_id,
        ):
            _raise_duplicate_relationship()
        raise
