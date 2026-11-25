"""Actor-aware write boundary for person-centric family relationships."""

from dataclasses import dataclass

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
from .services import (
    RelationshipInput,
    create_relationship,
    lock_relationship_mutations,
    update_relationship,
)

__all__ = (
    "PersonRelationshipInput",
    "create_person_relationship",
    "get_person_relationship_type_for_create",
    "get_person_relationship_for_update",
    "update_person_relationship",
)


_CREATE_KIND_CONFIGURATION = {
    "parent": ("biological_parent", "other_first"),
    "child": ("biological_parent", "person_first"),
    "partner": ("partner", "person_first"),
}


@dataclass(frozen=True, slots=True)
class PersonRelationshipInput:
    """Editable relationship attributes without type or participants."""

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


def _require_actor(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    updating: bool,
) -> AbstractBaseUser:
    permission = (
        "people.change_relationship"
        if updating
        else "people.add_relationship"
    )
    return require_active_actor_permission(
        actor=actor,
        permission=permission,
        denial_message="K zápisu této vazby nemáte oprávnění.",
    )


def _load_people(
    *person_ids: int,
    lock: bool,
) -> dict[int, Person]:
    if any(
        not isinstance(person_id, int) or isinstance(person_id, bool)
        for person_id in person_ids
    ):
        raise Person.DoesNotExist
    unique_ids = tuple(sorted(set(person_ids)))
    queryset = Person.objects.filter(pk__in=unique_ids).order_by("pk")
    if lock:
        queryset = queryset.select_for_update()
    people = {person.pk: person for person in queryset}
    if len(people) != len(unique_ids):
        raise Person.DoesNotExist
    return people


def _authorize_person(*, person: Person, actor: AbstractBaseUser) -> None:
    if (
        person.archived_at is not None
        or person.deleted_at is not None
        or not can_view_access_level(
            actor=actor,
            access_level=person.access_level,
        )
    ):
        raise Person.DoesNotExist


def _load_and_authorize_people(
    *,
    person: Person,
    other_person_id: int,
    actor: AbstractBaseUser,
) -> tuple[Person, Person]:
    if not isinstance(person, Person) or person.pk is None:
        raise Person.DoesNotExist
    people = _load_people(person.pk, other_person_id, lock=True)
    current_person = people[person.pk]
    other_person = people[other_person_id]
    _authorize_person(person=current_person, actor=actor)
    _authorize_person(person=other_person, actor=actor)
    return current_person, other_person


def _load_relationship_type(*, code: str) -> RelationshipType:
    try:
        relationship_type = RelationshipType.objects.select_for_update().get(
            code=code,
            is_system=True,
        )
    except RelationshipType.DoesNotExist:
        raise ValidationError(
            {
                "relationship_type": ValidationError(
                    "Požadovaný systémový typ vazby není dostupný.",
                    code="relationship_type_unavailable",
                )
            }
        ) from None
    if not relationship_type.is_active:
        raise ValidationError(
            {
                "relationship_type": ValidationError(
                    "Neaktivní typ vazby nelze použít.",
                    code="relationship_type_inactive",
                )
            }
        )
    return relationship_type


def get_person_relationship_type_for_create(
    *,
    relationship_kind: str,
) -> RelationshipType:
    """Return the fixed supported type for one person-centric action."""

    configuration = _CREATE_KIND_CONFIGURATION.get(relationship_kind)
    if configuration is None:
        raise RelationshipType.DoesNotExist
    type_code, _orientation = configuration
    try:
        return RelationshipType.objects.get(
            code=type_code,
            is_active=True,
            is_system=True,
        )
    except RelationshipType.DoesNotExist:
        raise RelationshipType.DoesNotExist from None


def _authorize_access_level(
    *,
    access_level: str,
    actor: AbstractBaseUser,
) -> None:
    if not can_view_access_level(
        actor=actor,
        access_level=access_level,
    ):
        raise PermissionDenied(
            "K nastavení této úrovně přístupu nemáte oprávnění."
        )


def _service_input(
    *,
    data: PersonRelationshipInput,
    relationship_type: RelationshipType,
    person_a: Person,
    person_b: Person,
) -> RelationshipInput:
    return RelationshipInput(
        relationship_type=relationship_type,
        person_a=person_a,
        person_b=person_b,
        note=data.note,
        access_level=data.access_level,
        verification_status=data.verification_status,
        date_precision=data.date_precision,
        date_qualifier=data.date_qualifier,
        start_year=data.start_year,
        start_month=data.start_month,
        start_day=data.start_day,
        end_year=data.end_year,
        end_month=data.end_month,
        end_day=data.end_day,
        original_date_text=data.original_date_text,
        date_note=data.date_note,
    )


@transaction.atomic
def create_person_relationship(
    *,
    person: Person,
    other_person_id: int,
    relationship_kind: str,
    data: PersonRelationshipInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Create one fixed-type relationship after current-state checks."""

    configuration = _CREATE_KIND_CONFIGURATION.get(relationship_kind)
    if configuration is None:
        raise ValidationError(
            {
                "relationship_type": ValidationError(
                    "Tento způsob vytvoření vazby není podporován.",
                    code="relationship_kind_unsupported",
                )
            }
        )
    current_actor = _require_actor(actor=actor, updating=False)
    lock_relationship_mutations()
    type_code, orientation = configuration
    relationship_type = _load_relationship_type(code=type_code)
    current_person, other_person = _load_and_authorize_people(
        person=person,
        other_person_id=other_person_id,
        actor=current_actor,
    )
    _authorize_access_level(
        access_level=data.access_level,
        actor=current_actor,
    )
    person_a, person_b = (
        (other_person, current_person)
        if orientation == "other_first"
        else (current_person, other_person)
    )
    current_actor = _require_actor(actor=actor, updating=False)
    return create_relationship(
        data=_service_input(
            data=data,
            relationship_type=relationship_type,
            person_a=person_a,
            person_b=person_b,
        ),
        created_by=current_actor,
    )


def _load_relationship_context(
    *,
    person: Person,
    relationship: Relationship,
    actor: AbstractBaseUser,
    lock: bool,
) -> tuple[Person, Relationship]:
    if (
        not isinstance(person, Person)
        or person.pk is None
        or not isinstance(relationship, Relationship)
        or relationship.pk is None
    ):
        raise Relationship.DoesNotExist
    try:
        if lock:
            candidate = Relationship.objects.select_for_update().get(
                pk=relationship.pk
            )
            relationship_type = (
                RelationshipType.objects.select_for_update().get(
                    pk=candidate.relationship_type_id
                )
            )
            people = _load_people(
                candidate.person_a_id,
                candidate.person_b_id,
                lock=True,
            )
            candidate.relationship_type = relationship_type
            candidate.person_a = people[candidate.person_a_id]
            candidate.person_b = people[candidate.person_b_id]
        else:
            candidate = (
                Relationship.objects.select_related(
                    "relationship_type",
                    "person_a",
                    "person_b",
                ).get(pk=relationship.pk)
            )
    except Relationship.DoesNotExist:
        raise Relationship.DoesNotExist from None
    if person.pk not in (candidate.person_a_id, candidate.person_b_id):
        raise Relationship.DoesNotExist
    current_person = (
        candidate.person_a
        if candidate.person_a_id == person.pk
        else candidate.person_b
    )
    _authorize_person(person=current_person, actor=actor)
    if (
        candidate.archived_at is not None
        or candidate.deleted_at is not None
        or not can_view_access_level(
            actor=actor,
            access_level=candidate.access_level,
        )
    ):
        raise Relationship.DoesNotExist
    _authorize_person(person=candidate.person_a, actor=actor)
    _authorize_person(person=candidate.person_b, actor=actor)
    return current_person, candidate


def get_person_relationship_for_update(
    *,
    person: Person,
    relationship: Relationship,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Return one editable relationship without exposing hidden context."""

    current_actor = _require_actor(actor=actor, updating=True)
    _current_person, candidate = _load_relationship_context(
        person=person,
        relationship=relationship,
        actor=current_actor,
        lock=False,
    )
    return candidate


@transaction.atomic
def update_person_relationship(
    *,
    person: Person,
    relationship: Relationship,
    data: PersonRelationshipInput,
    actor: AbstractBaseUser | AnonymousUser,
) -> Relationship:
    """Update attributes while preserving relationship type and people."""

    current_actor = _require_actor(actor=actor, updating=True)
    lock_relationship_mutations()
    _current_person, candidate = _load_relationship_context(
        person=person,
        relationship=relationship,
        actor=current_actor,
        lock=True,
    )
    _authorize_access_level(
        access_level=candidate.access_level,
        actor=current_actor,
    )
    _authorize_access_level(
        access_level=data.access_level,
        actor=current_actor,
    )
    _require_actor(actor=actor, updating=True)
    return update_relationship(
        relationship=candidate,
        data=_service_input(
            data=data,
            relationship_type=candidate.relationship_type,
            person_a=candidate.person_a,
            person_b=candidate.person_b,
        ),
    )
