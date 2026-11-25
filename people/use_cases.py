"""Actor-aware person relationship write boundary."""

from dataclasses import asdict, dataclass
from typing import NoReturn

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from common.choices import (
    AccessLevel,
    DatePrecision,
    DateQualifier,
    VerificationStatus,
)
from common.permissions import (
    can_view_access_level,
    require_active_actor_permission,
)

from .models import Person, Relationship, RelationshipType
# Sdílený zámek zápisů vztahů je interní detail stejné aplikace.
from .services import (
    RelationshipInput,
    _lock_relationship_mutations,
    create_relationship,
    update_relationship,
)

__all__ = (
    "PERSON_RELATIONSHIP_KINDS",
    "RelationshipDetailsInput",
    "PERSON_RELATIONSHIP_TYPE_CODES",
    "create_person_relationship",
    "get_person_relationship_for_update",
    "update_person_relationship",
)

# Druh akce z pohledu osoby -> systémový typ vazby.
PERSON_RELATIONSHIP_KINDS = {
    "parent": "biological_parent",
    "child": "biological_parent",
    "partner": "partner",
}
PERSON_RELATIONSHIP_TYPE_CODES = frozenset(PERSON_RELATIONSHIP_KINDS.values())


@dataclass(frozen=True, slots=True)
class RelationshipDetailsInput:
    """Údaje vazby upravitelné uživatelem; typ a účastníci sem nepatří."""

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


def _relationship_input(
    *,
    details: RelationshipDetailsInput,
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
) -> RelationshipInput:
    return RelationshipInput(
        relationship_type=relationship_type,
        person_a=person_a,
        person_b=person_b,
        **asdict(details),
    )


def _raise_relationship_error(
    key: str,
    message: str,
    code: str,
) -> NoReturn:
    raise ValidationError({key: ValidationError(message, code=code)})


_DUPLICATE_RELATIONSHIP_MESSAGE = (
    "Stejná vazba se stejným časovým vymezením již existuje."
)


def _with_readable_duplicate_error(error: ValidationError) -> ValidationError:
    """Nahraď obecnou hlášku porušeného omezení srozumitelnou zprávou."""

    if not hasattr(error, "error_dict"):
        return error
    errors = {
        field: [
            ValidationError(
                _DUPLICATE_RELATIONSHIP_MESSAGE,
                code="duplicate_relationship",
            )
            if item.code == "duplicate_relationship"
            else item
            for item in items
        ]
        for field, items in error.error_dict.items()
    }
    return ValidationError(errors)


def _require_actor(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    updating: bool,
) -> AbstractBaseUser:
    return require_active_actor_permission(
        actor=actor,
        permission=(
            "people.change_relationship"
            if updating
            else "people.add_relationship"
        ),
        denial_message="K zápisu tohoto vztahu nemáte oprávnění.",
    )


def _is_accessible_person(*, person: Person, actor: AbstractBaseUser) -> bool:
    return (
        person.archived_at is None
        and person.deleted_at is None
        and can_view_access_level(
            actor=actor,
            access_level=person.access_level,
        )
    )


def _lock_people(*people: Person) -> dict[int, Person]:
    """Zamkni předané osoby v pořadí primárních klíčů.

    Všechny zápisy vztahů jsou předem serializované společným zámkem
    ``_lock_relationship_mutations``, proto pořadí mezi jednotlivými voláními
    nemůže vést k deadlocku.
    """

    person_ids = sorted({person.pk for person in people if person.pk})
    return {
        person.pk: person
        for person in Person.objects.select_for_update()
        .filter(pk__in=person_ids)
        .order_by("pk")
    }


def _load_person(person: Person, actor: AbstractBaseUser) -> Person:
    if not isinstance(person, Person) or person.pk is None:
        raise Person.DoesNotExist
    current = _lock_people(person).get(person.pk)
    if current is None or not _is_accessible_person(
        person=current,
        actor=actor,
    ):
        raise Person.DoesNotExist
    return current


def _load_counterpart(
    *,
    counterpart: Person | None,
    person: Person,
    actor: AbstractBaseUser,
) -> Person:
    message = "Vybranou osobu nelze pro tento vztah použít."
    if (
        not isinstance(counterpart, Person)
        or counterpart.pk is None
        or counterpart.pk == person.pk
    ):
        _raise_relationship_error(
            "counterpart",
            message,
            "relationship_counterpart_unavailable",
        )
    current = _lock_people(counterpart).get(counterpart.pk)
    if current is None or not _is_accessible_person(
        person=current,
        actor=actor,
    ):
        _raise_relationship_error(
            "counterpart",
            message,
            "relationship_counterpart_unavailable",
        )
    return current


def _load_relationship_type(code: str) -> RelationshipType:
    try:
        return RelationshipType.objects.select_for_update().get(
            code=code,
            is_system=True,
        )
    except RelationshipType.DoesNotExist:
        _raise_relationship_error(
            "relationship_type",
            "Požadovaný systémový typ vazby není dostupný.",
            "relationship_type_unavailable",
        )


def _authorize_proposed_access(
    *,
    data: RelationshipDetailsInput,
    actor: AbstractBaseUser,
) -> None:
    if not can_view_access_level(actor=actor, access_level=data.access_level):
        raise PermissionDenied(
            "K nastavení této úrovně přístupu nemáte oprávnění."
        )


def _load_relationship_context(
    *,
    relationship: Relationship,
    person: Person,
    actor: AbstractBaseUser,
) -> Relationship:
    """Vrať upravitelnou vazbu, jinak jednotně selži bez prozrazení stavu."""

    if not isinstance(relationship, Relationship) or relationship.pk is None:
        raise Relationship.DoesNotExist
    try:
        candidate = (
            Relationship.objects.select_for_update()
            .select_related("relationship_type")
            .get(pk=relationship.pk)
        )
    except Relationship.DoesNotExist:
        raise Relationship.DoesNotExist from None
    if (
        candidate.deleted_at is not None
        or candidate.archived_at is not None
        or person.pk not in (candidate.person_a_id, candidate.person_b_id)
        or candidate.relationship_type.code
        not in PERSON_RELATIONSHIP_TYPE_CODES
        or not candidate.relationship_type.is_system
        or not can_view_access_level(
            actor=actor,
            access_level=candidate.access_level,
        )
    ):
        raise Relationship.DoesNotExist
    people = _lock_people(
        Person(pk=candidate.person_a_id),
        Person(pk=candidate.person_b_id),
    )
    for person_id in (candidate.person_a_id, candidate.person_b_id):
        participant = people.get(person_id)
        if participant is None or not _is_accessible_person(
            person=participant,
            actor=actor,
        ):
            raise Relationship.DoesNotExist
    candidate.person_a = people[candidate.person_a_id]
    candidate.person_b = people[candidate.person_b_id]
    return candidate


@transaction.atomic
def create_person_relationship(
    *,
    person: Person,
    kind: str,
    counterpart: Person | None,
    data: RelationshipDetailsInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Vytvoř rodičovskou nebo partnerskou vazbu z pohledu jedné osoby.

    Typ vazby i orientaci osob určuje výhradně ``kind``.
    """

    current_actor = _require_actor(actor=actor, updating=False)
    if kind not in PERSON_RELATIONSHIP_KINDS:
        _raise_relationship_error(
            "relationship_type",
            "Toto rozhraní podporuje pouze rodiče, dítě a partnera.",
            "relationship_kind_unsupported",
        )
    _lock_relationship_mutations()
    current_person = _load_person(person, current_actor)
    current_counterpart = _load_counterpart(
        counterpart=counterpart,
        person=current_person,
        actor=current_actor,
    )
    relationship_type = _load_relationship_type(
        PERSON_RELATIONSHIP_KINDS[kind]
    )
    _authorize_proposed_access(data=data, actor=current_actor)
    person_a, person_b = (
        (current_counterpart, current_person)
        if kind == "parent"
        else (current_person, current_counterpart)
    )
    current_actor = _require_actor(actor=actor, updating=False)
    try:
        return create_relationship(
            data=_relationship_input(
                details=data,
                relationship_type=relationship_type,
                person_a=person_a,
                person_b=person_b,
            ),
            created_by=current_actor,
        )
    except ValidationError as error:
        raise _with_readable_duplicate_error(error) from None


@transaction.atomic
def get_person_relationship_for_update(
    *,
    person: Person,
    relationship: Relationship,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Vrať aktuálně upravitelnou vazbu osoby bez úniku skrytého stavu."""

    current_actor = _require_actor(actor=actor, updating=True)
    current_person = _load_person(person, current_actor)
    return _load_relationship_context(
        relationship=relationship,
        person=current_person,
        actor=current_actor,
    )


@transaction.atomic
def update_person_relationship(
    *,
    person: Person,
    relationship: Relationship,
    data: RelationshipDetailsInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Změň údaje vazby; typ ani účastníci se nemění."""

    current_actor = _require_actor(actor=actor, updating=True)
    _lock_relationship_mutations()
    current_person = _load_person(person, current_actor)
    candidate = _load_relationship_context(
        relationship=relationship,
        person=current_person,
        actor=current_actor,
    )
    _authorize_proposed_access(data=data, actor=current_actor)
    current_actor = _require_actor(actor=actor, updating=True)
    try:
        return update_relationship(
            relationship=candidate,
            data=_relationship_input(
                details=data,
                relationship_type=candidate.relationship_type,
                person_a=candidate.person_a,
                person_b=candidate.person_b,
            ),
        )
    except ValidationError as error:
        raise _with_readable_duplicate_error(error) from None
