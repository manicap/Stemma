"""Doménové služby aplikace people."""

from dataclasses import dataclass
from typing import NoReturn

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    Gender,
    VerificationStatus,
)
from common.permissions import can_view_access_level

from .models import Person, PersonCategory, Relationship, RelationshipType

__all__ = (
    "BasicPersonInput",
    "PersonInput",
    "RelationshipInput",
    "create_person",
    "create_relationship",
    "update_person",
    "update_person_basic",
    "update_relationship",
)

_PARENT_RELATIONSHIP_TYPE_CODES = frozenset(
    {
        "biological_parent",
        "adoptive_parent",
        "step_parent",
        "foster_parent",
    }
)


@dataclass(frozen=True, slots=True)
class BasicPersonInput:
    """Úplný snapshot údajů zpřístupněných základním formulářem."""

    category: PersonCategory | None = None
    gender: str = Gender.UNKNOWN
    first_name: str = ""
    last_name: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PersonInput:
    """Úplný vstup základních editovatelných údajů osoby."""

    category: PersonCategory | None = None
    gender: str = Gender.UNKNOWN
    first_name: str = ""
    last_name: str = ""
    title_before_name: str = ""
    title_after_name: str = ""
    notes: str = ""
    biography: str = ""
    access_level: str = AccessLevel.PUBLIC
    verification_status: str = VerificationStatus.UNCONFIRMED


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


def _load_person_category(
    category: PersonCategory | None,
) -> PersonCategory | None:
    if category is None:
        return None
    if category.pk is None:
        _raise_service_error(
            "category",
            "Kategorie osoby musí být uložená v databázi.",
            "person_category_unsaved",
        )
    try:
        return PersonCategory.objects.get(pk=category.pk)
    except PersonCategory.DoesNotExist:
        _raise_service_error(
            "category",
            "Kategorie osoby musí být uložená v databázi.",
            "person_category_unsaved",
        )


def _load_person_created_by(
    created_by: AbstractBaseUser | None,
) -> AbstractBaseUser | None:
    if created_by is None:
        return None
    if created_by.pk is None:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "person_created_by_unsaved",
        )
    user_model = get_user_model()
    try:
        return user_model._default_manager.get(pk=created_by.pk)
    except user_model.DoesNotExist:
        _raise_service_error(
            "created_by",
            "Autor musí být uložený v databázi.",
            "person_created_by_unsaved",
        )


def create_person(
    *,
    data: PersonInput,
    created_by: AbstractBaseUser | None = None,
) -> Person:
    """Atomicky vytvoř osobu přes validační doménovou hranici."""

    with transaction.atomic():
        person = Person(
            category=_load_person_category(data.category),
            gender=data.gender,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            title_before_name=data.title_before_name.strip(),
            title_after_name=data.title_after_name.strip(),
            notes=data.notes.strip(),
            biography=data.biography.strip(),
            access_level=data.access_level,
            verification_status=data.verification_status,
            created_by=_load_person_created_by(created_by),
        )
        person.full_clean()
        person.save()
        return Person.objects.select_related("category", "created_by").get(
            pk=person.pk
        )


def update_person(
    *,
    person: Person,
    data: PersonInput,
    actor: AbstractBaseUser,
) -> Person:
    """Atomicky a autorizovaně změň základní údaje osoby."""

    with transaction.atomic():
        current = _load_person_for_update(
            person=person,
            actor=actor,
        )
        _apply_basic_person_input(current=current, data=data)
        current.title_before_name = data.title_before_name.strip()
        current.title_after_name = data.title_after_name.strip()
        current.biography = data.biography.strip()
        return _validate_save_and_reload_person(current)


def update_person_basic(
    *,
    person: Person,
    data: BasicPersonInput,
    actor: AbstractBaseUser,
) -> Person:
    """Změň jen pole v základním formuláři a ostatní zachovej z DB."""

    with transaction.atomic():
        current = _load_person_for_update(
            person=person,
            actor=actor,
        )
        _apply_basic_person_input(current=current, data=data)
        return _validate_save_and_reload_person(current)


def _load_person_for_update(
    *,
    person: Person,
    actor: AbstractBaseUser,
) -> Person:
    """Ověř actora a vrať čerstvou uzamčenou editovatelnou osobu."""

    if person.pk is None:
        _raise_service_error(
            "person",
            "Osoba musí být uložená v databázi.",
            "person_unsaved",
        )

    user_model = get_user_model()
    if not getattr(actor, "is_authenticated", False) or actor.pk is None:
        raise PermissionDenied("K úpravě osoby nemáte oprávnění.")
    try:
        current_actor = user_model._default_manager.get(pk=actor.pk)
    except user_model.DoesNotExist as exc:
        raise PermissionDenied(
            "K úpravě osoby nemáte oprávnění."
        ) from exc
    if (
        not current_actor.is_active
        or not current_actor.has_perm("people.change_person")
    ):
        raise PermissionDenied("K úpravě osoby nemáte oprávnění.")

    try:
        current = Person.objects.select_for_update().get(pk=person.pk)
    except Person.DoesNotExist:
        _raise_service_error(
            "person",
            "Osoba musí být uložená v databázi.",
            "person_unsaved",
        )
    if (
        current.archived_at is not None
        or current.deleted_at is not None
        or not can_view_access_level(
            actor=current_actor,
            access_level=current.access_level,
        )
    ):
        raise Person.DoesNotExist
    return current


def _apply_basic_person_input(
    *,
    current: Person,
    data: BasicPersonInput | PersonInput,
) -> None:
    current.category = _load_person_category(data.category)
    current.gender = data.gender
    current.first_name = data.first_name.strip()
    current.last_name = data.last_name.strip()
    current.notes = data.notes.strip()


def _validate_save_and_reload_person(current: Person) -> Person:
    current.full_clean()
    current.save()
    return Person.objects.select_related("category", "created_by").get(
        pk=current.pk
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


def _lock_relationship_mutations() -> None:
    """Serializuj vztahové zápisy společným prvním řádkovým zámkem."""

    sentinel_ids = list(
        RelationshipType.objects.select_for_update()
        .filter(
            code__in=_PARENT_RELATIONSHIP_TYPE_CODES,
            is_system=True,
        )
        .order_by("pk")
        .values_list("pk", flat=True)[:1]
    )
    if not sentinel_ids:
        _raise_service_error(
            "relationship_type",
            "Chybí systémová konfigurace pro bezpečný zápis vazby.",
            "relationship_configuration_invalid",
        )


def _load_relationship_people(
    person_a: Person,
    person_b: Person,
) -> tuple[Person, Person]:
    """Načti a zamkni obě osoby vždy ve stejném pořadí primárních klíčů."""

    specifications = (
        (
            "person_a",
            "relationship_person_a_unsaved",
            person_a,
        ),
        (
            "person_b",
            "relationship_person_b_unsaved",
            person_b,
        ),
    )
    if person_a.pk is None:
        _raise_service_error(
            "person_a",
            "Osoba musí být uložená v databázi.",
            "relationship_person_a_unsaved",
        )

    person_ids = sorted(
        {
            person.pk
            for person in (person_a, person_b)
            if person.pk is not None
        }
    )
    people_by_id = {
        person.pk: person
        for person in Person.objects.select_for_update()
        .filter(pk__in=person_ids)
        .order_by("pk")
    }
    for key, code, person in specifications:
        if person.pk is None or person.pk not in people_by_id:
            _raise_service_error(
                key,
                "Osoba musí být uložená v databázi.",
                code,
            )

    return people_by_id[person_a.pk], people_by_id[person_b.pk]


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


def _validate_parent_relationship_cycle(
    *,
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
    exclude_relationship_id: int | None = None,
) -> None:
    if (
        relationship_type.code not in _PARENT_RELATIONSHIP_TYPE_CODES
        or person_a.pk == person_b.pk
    ):
        return

    relationships = Relationship.objects.select_for_update().filter(
        deleted_at__isnull=True,
        relationship_type__code__in=_PARENT_RELATIONSHIP_TYPE_CODES,
    )
    if exclude_relationship_id is not None:
        relationships = relationships.exclude(pk=exclude_relationship_id)

    adjacency: dict[int, set[int]] = {}
    for parent_id, child_id in relationships.values_list(
        "person_a_id",
        "person_b_id",
    ):
        adjacency.setdefault(parent_id, set()).add(child_id)

    target_id = person_a.pk
    pending = [person_b.pk]
    visited: set[int] = set()

    while pending:
        current_id = pending.pop()
        if current_id == target_id:
            raise ValidationError(
                {
                    "person_b": ValidationError(
                        "Tato rodičovská vazba by vytvořila cyklus.",
                        code="relationship_parent_cycle",
                        params={
                            "person_a_id": person_a.pk,
                            "person_b_id": person_b.pk,
                            "relationship_type_id": relationship_type.pk,
                            "relationship_type_code": (
                                relationship_type.code
                            ),
                        },
                    )
                }
            )
        if current_id in visited:
            continue
        visited.add(current_id)
        pending.extend(adjacency.get(current_id, ()))


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
            _lock_relationship_mutations()
            relationship_type = _load_relationship_type(
                data.relationship_type
            )
            person_a, person_b = _load_relationship_people(
                data.person_a,
                data.person_b,
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
            _validate_parent_relationship_cycle(
                relationship_type=relationship_type,
                person_a=person_a,
                person_b=person_b,
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
            _lock_relationship_mutations()
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
            person_a, person_b = _load_relationship_people(
                data.person_a,
                data.person_b,
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
            _validate_parent_relationship_cycle(
                relationship_type=relationship_type,
                person_a=person_a,
                person_b=person_b,
                exclude_relationship_id=relationship_id,
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
