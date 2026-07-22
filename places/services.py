"""Doménové služby aplikace places."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from people.models import Person

from .models import Place, Residence, ResidenceType

__all__ = (
    "ResidenceInput",
    "create_residence",
    "update_residence",
)


@dataclass(frozen=True, slots=True)
class ResidenceInput:
    """Úplný snapshot editovatelných údajů jednoho bydliště."""

    person: Person
    residence_type: ResidenceType
    place: Place | None = None
    address_text: str = ""
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


def _load_person(person: Person) -> Person:
    if person.pk is None:
        _raise_service_error(
            "person",
            "Osoba musí být uložená v databázi.",
            "residence_person_unsaved",
        )

    try:
        return Person.objects.select_for_update().get(pk=person.pk)
    except Person.DoesNotExist:
        _raise_service_error(
            "person",
            "Osoba musí být uložená v databázi.",
            "residence_person_unsaved",
        )


def _load_residence_type(
    residence_type: ResidenceType,
) -> ResidenceType:
    if residence_type.pk is None:
        _raise_service_error(
            "residence_type",
            "Typ bydliště musí být uložený v databázi.",
            "residence_type_unsaved",
        )

    try:
        return ResidenceType.objects.select_for_update().get(
            pk=residence_type.pk
        )
    except ResidenceType.DoesNotExist:
        _raise_service_error(
            "residence_type",
            "Typ bydliště musí být uložený v databázi.",
            "residence_type_unsaved",
        )


def _load_place(place: Place | None) -> Place | None:
    if place is None:
        return None
    if place.pk is None:
        _raise_service_error(
            "place",
            "Místo musí být uložené v databázi.",
            "residence_place_unsaved",
        )

    try:
        return Place.objects.select_for_update().get(pk=place.pk)
    except Place.DoesNotExist:
        _raise_service_error(
            "place",
            "Místo musí být uložené v databázi.",
            "residence_place_unsaved",
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
            "residence_created_by_unsaved",
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
            "residence_created_by_unsaved",
        )


def _apply_input(
    residence: Residence,
    *,
    data: ResidenceInput,
    person: Person,
    residence_type: ResidenceType,
    place: Place | None,
) -> None:
    residence.person = person
    residence.residence_type = residence_type
    residence.place = place
    residence.address_text = data.address_text.strip()
    residence.note = data.note.strip()
    residence.access_level = data.access_level
    residence.verification_status = data.verification_status
    residence.date_precision = data.date_precision
    residence.date_qualifier = data.date_qualifier
    residence.start_year = data.start_year
    residence.start_month = data.start_month
    residence.start_day = data.start_day
    residence.end_year = data.end_year
    residence.end_month = data.end_month
    residence.end_day = data.end_day
    residence.original_date_text = data.original_date_text.strip()
    residence.date_note = data.date_note.strip()


def _reload_residence(residence_id: int) -> Residence:
    return Residence.objects.select_related(
        "person",
        "residence_type",
        "place",
        "created_by",
    ).get(pk=residence_id)


def create_residence(
    *,
    data: ResidenceInput,
    created_by: AbstractBaseUser | None = None,
) -> Residence:
    """Atomicky vytvoř a vrať čerstvě načtené bydliště."""

    with transaction.atomic():
        person = _load_person(data.person)
        residence_type = _load_residence_type(data.residence_type)
        place = _load_place(data.place)
        current_created_by = _load_created_by(created_by)

        if not residence_type.is_active:
            _raise_service_error(
                "residence_type",
                "Neaktivní typ bydliště nelze použít pro nový záznam.",
                "residence_type_inactive",
            )

        candidate = Residence(created_by=current_created_by)
        _apply_input(
            candidate,
            data=data,
            person=person,
            residence_type=residence_type,
            place=place,
        )
        candidate.full_clean()
        candidate.save()
        return _reload_residence(candidate.pk)


def update_residence(
    *,
    residence: Residence,
    data: ResidenceInput,
) -> Residence:
    """Atomicky změň a vrať čerstvě načtené bydliště."""

    if residence.pk is None:
        _raise_service_error(
            "residence",
            "Bydliště musí být uložené v databázi.",
            "residence_unsaved",
        )

    residence_id = residence.pk
    with transaction.atomic():
        try:
            candidate = Residence.objects.select_for_update().get(
                pk=residence_id
            )
        except Residence.DoesNotExist:
            _raise_service_error(
                "residence",
                "Bydliště musí být uložené v databázi.",
                "residence_unsaved",
            )

        if candidate.deleted_at is not None:
            _raise_service_error(
                "residence",
                "Měkce odstraněné bydliště nelze upravit.",
                "residence_deleted",
            )

        original_residence_type_id = candidate.residence_type_id
        person = _load_person(data.person)
        residence_type = _load_residence_type(data.residence_type)
        place = _load_place(data.place)

        if (
            not residence_type.is_active
            and residence_type.pk != original_residence_type_id
        ):
            _raise_service_error(
                "residence_type",
                "Na jiný neaktivní typ bydliště nelze přejít.",
                "residence_type_inactive",
            )

        _apply_input(
            candidate,
            data=data,
            person=person,
            residence_type=residence_type,
            place=place,
        )
        candidate.full_clean()
        candidate.save()
        return _reload_residence(candidate.pk)
