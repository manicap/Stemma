"""Čtecí doménové dotazy aplikace people."""

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, QuerySet, Subquery

from common.choices import AccessLevel, Gender
from common.permissions import can_view_access_level

from .models import Person, Relationship

__all__ = (
    "RelationshipOverviewItem",
    "RelationshipOverviewReason",
    "SiblingOverviewItem",
    "get_biological_siblings",
    "get_relationship_overview",
    "get_sibling_overview",
    "get_visible_relationship_overview",
)

_SIBLING_REASON_ORDER = (
    "biological",
    "sibling",
    "adoptive_sibling",
    "step_sibling",
    "social_sibling",
)
_EXPLICIT_SIBLING_CODES = _SIBLING_REASON_ORDER[1:]
_RELATIONSHIP_CATEGORY_ORDER = (
    "parent_child",
    "partner",
    "sibling",
    "godparent",
    "care",
    "social",
    "other",
)
_RELATIONSHIP_CATEGORY_RANK = {
    category: rank
    for rank, category in enumerate(_RELATIONSHIP_CATEGORY_ORDER)
}
_ACCESS_LEVELS = (
    AccessLevel.PUBLIC,
    AccessLevel.AUTHENTICATED,
    AccessLevel.RESTRICTED,
    AccessLevel.ADMIN_ONLY,
)
_VIEW_ARCHIVED_PERSON_PERMISSION = "people.view_archived_person"
_VIEW_DELETED_PERSON_PERMISSION = "people.view_deleted_person"


@dataclass(frozen=True, slots=True)
class RelationshipOverviewReason:
    """Jeden deduplikovaný důvod vazby včetně explicitní provenance."""

    category: str
    relationship_code: str
    label: str
    relationship_ids: tuple[int, ...]
    is_derived: bool


@dataclass(frozen=True, slots=True)
class RelationshipOverviewItem:
    """Jedna související osoba a všechny důvody její vazby."""

    person: Person
    reasons: tuple[RelationshipOverviewReason, ...]


@dataclass(frozen=True, slots=True)
class SiblingOverviewItem:
    """Osoba a všechny důvody její sourozenecké vazby."""

    person: Person
    relationship_codes: tuple[str, ...]


@dataclass(slots=True)
class _RelationshipReasonAccumulator:
    category: str
    relationship_code: str
    label: str
    relationship_ids: set[int]
    is_derived: bool
    sort_order: int


def get_biological_siblings(
    *,
    person: Person,
) -> QuerySet[Person]:
    """Vrať biologické sourozence odvozené ze společného rodiče."""

    if person.pk is None or not Person.objects.filter(pk=person.pk).exists():
        raise ValidationError(
            {
                "person": ValidationError(
                    "Osoba musí být před vyhledáním sourozenců uložena.",
                    code="person_unsaved",
                )
            }
        )

    biological_parent_ids = Relationship.objects.filter(
        deleted_at__isnull=True,
        relationship_type__code="biological_parent",
        person_b_id=person.pk,
    ).values("person_a_id")
    biological_sibling_ids = Relationship.objects.filter(
        deleted_at__isnull=True,
        relationship_type__code="biological_parent",
        person_a_id__in=Subquery(biological_parent_ids),
    ).values("person_b_id")

    return (
        Person.objects.filter(
            deleted_at__isnull=True,
            pk__in=Subquery(biological_sibling_ids),
        )
        .exclude(pk=person.pk)
        .distinct()
    )


def get_sibling_overview(
    *,
    person: Person,
) -> tuple[SiblingOverviewItem, ...]:
    """Vrať agregovaný přehled biologických a explicitních sourozenců."""

    people_by_id: dict[int, Person] = {}
    reasons_by_person_id: dict[int, set[str]] = {}

    for sibling in get_biological_siblings(person=person):
        people_by_id[sibling.pk] = sibling
        reasons_by_person_id.setdefault(sibling.pk, set()).add(
            "biological"
        )

    explicit_relationships = Relationship.objects.filter(
        Q(person_a=person) | Q(person_b=person),
        deleted_at__isnull=True,
        relationship_type__code__in=_EXPLICIT_SIBLING_CODES,
    ).select_related(
        "relationship_type",
        "person_a",
        "person_b",
    )
    for relationship in explicit_relationships:
        sibling = (
            relationship.person_b
            if relationship.person_a_id == person.pk
            else relationship.person_a
        )
        if sibling.pk == person.pk or sibling.deleted_at is not None:
            continue

        people_by_id[sibling.pk] = sibling
        reasons_by_person_id.setdefault(sibling.pk, set()).add(
            relationship.relationship_type.code
        )

    items = (
        SiblingOverviewItem(
            person=sibling,
            relationship_codes=tuple(
                reason
                for reason in _SIBLING_REASON_ORDER
                if reason in reasons_by_person_id[sibling_id]
            ),
        )
        for sibling_id, sibling in people_by_id.items()
    )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.person.last_name,
                item.person.first_name,
                item.person.pk,
            ),
        )
    )


def _relationship_label(
    relationship: Relationship,
    *,
    person_id: int,
    other_person: Person,
) -> str:
    direction = (
        "forward"
        if relationship.person_a_id == person_id
        else "reverse"
    )
    gender_suffix = {
        Gender.MALE: "male",
        Gender.FEMALE: "female",
    }.get(other_person.gender, "unknown")
    return getattr(
        relationship.relationship_type,
        f"{direction}_label_{gender_suffix}",
    )


def _biological_sibling_label(person: Person) -> str:
    return {
        Gender.MALE: "Biologický bratr",
        Gender.FEMALE: "Biologická sestra",
    }.get(person.gender, "Biologický sourozenec")


def _add_relationship_reason(
    *,
    reasons_by_person_id: dict[
        int,
        dict[tuple[str, str, str], _RelationshipReasonAccumulator],
    ],
    person_id: int,
    category: str,
    relationship_code: str,
    label: str,
    relationship_id: int | None,
    is_derived: bool,
    sort_order: int,
) -> None:
    identity = (category, relationship_code, label)
    reasons = reasons_by_person_id.setdefault(person_id, {})
    accumulator = reasons.get(identity)
    if accumulator is None:
        accumulator = _RelationshipReasonAccumulator(
            category=category,
            relationship_code=relationship_code,
            label=label,
            relationship_ids=set(),
            is_derived=is_derived,
            sort_order=sort_order,
        )
        reasons[identity] = accumulator
    if relationship_id is not None:
        accumulator.relationship_ids.add(relationship_id)


def _reason_sort_key(
    reason: _RelationshipReasonAccumulator,
) -> tuple[int, str, int, int, str, str]:
    category_rank = _RELATIONSHIP_CATEGORY_RANK.get(reason.category)
    category_is_unknown = category_rank is None
    return (
        len(_RELATIONSHIP_CATEGORY_ORDER)
        if category_is_unknown
        else category_rank,
        reason.category if category_is_unknown else "",
        0
        if (
            reason.category == "sibling"
            and reason.relationship_code == "biological"
            and reason.is_derived
        )
        else 1,
        reason.sort_order,
        reason.relationship_code,
        reason.label,
    )


def get_relationship_overview(
    *,
    person: Person,
) -> tuple[RelationshipOverviewItem, ...]:
    """Vrať celkový interní přehled vztahů osoby s provenance."""

    sibling_overview = get_sibling_overview(person=person)
    people_by_id: dict[int, Person] = {
        item.person.pk: item.person for item in sibling_overview
    }
    reasons_by_person_id: dict[
        int,
        dict[tuple[str, str, str], _RelationshipReasonAccumulator],
    ] = {}

    explicit_sibling_reasons = {
        (item.person.pk, relationship_code)
        for item in sibling_overview
        for relationship_code in item.relationship_codes
        if relationship_code != "biological"
    }
    for item in sibling_overview:
        if "biological" not in item.relationship_codes:
            continue
        _add_relationship_reason(
            reasons_by_person_id=reasons_by_person_id,
            person_id=item.person.pk,
            category="sibling",
            relationship_code="biological",
            label=_biological_sibling_label(item.person),
            relationship_id=None,
            is_derived=True,
            sort_order=-1,
        )

    sibling_relationships = Relationship.objects.filter(
        Q(person_a=person) | Q(person_b=person),
        deleted_at__isnull=True,
        relationship_type__code__in=_EXPLICIT_SIBLING_CODES,
    ).select_related(
        "relationship_type",
        "person_a",
        "person_b",
    )
    other_relationships = Relationship.objects.filter(
        Q(person_a=person) | Q(person_b=person),
        deleted_at__isnull=True,
    ).exclude(
        relationship_type__code__in=_EXPLICIT_SIBLING_CODES,
    ).select_related(
        "relationship_type",
        "person_a",
        "person_b",
    )

    for relationship in (*sibling_relationships, *other_relationships):
        other_person = (
            relationship.person_b
            if relationship.person_a_id == person.pk
            else relationship.person_a
        )
        if other_person.pk == person.pk or other_person.deleted_at is not None:
            continue

        relationship_code = relationship.relationship_type.code
        if (
            relationship_code in _EXPLICIT_SIBLING_CODES
            and (other_person.pk, relationship_code)
            not in explicit_sibling_reasons
        ):
            continue

        people_by_id[other_person.pk] = other_person
        _add_relationship_reason(
            reasons_by_person_id=reasons_by_person_id,
            person_id=other_person.pk,
            category=relationship.relationship_type.category,
            relationship_code=relationship_code,
            label=_relationship_label(
                relationship,
                person_id=person.pk,
                other_person=other_person,
            ),
            relationship_id=relationship.pk,
            is_derived=False,
            sort_order=relationship.relationship_type.sort_order,
        )

    items = []
    for person_id, other_person in people_by_id.items():
        accumulators = reasons_by_person_id.get(person_id, {}).values()
        reasons = tuple(
            RelationshipOverviewReason(
                category=reason.category,
                relationship_code=reason.relationship_code,
                label=reason.label,
                relationship_ids=tuple(sorted(reason.relationship_ids)),
                is_derived=reason.is_derived,
            )
            for reason in sorted(accumulators, key=_reason_sort_key)
        )
        if reasons:
            items.append(
                RelationshipOverviewItem(
                    person=other_person,
                    reasons=reasons,
                )
            )

    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.person.last_name,
                item.person.first_name,
                item.person.pk,
            ),
        )
    )


def _raise_person_unsaved() -> None:
    raise ValidationError(
        {
            "person": ValidationError(
                "Osoba musí být před vyhledáním sourozenců uložena.",
                code="person_unsaved",
            )
        }
    )


def _load_current_person(person: Person) -> Person:
    person_id = getattr(person, "pk", None)
    if person_id is None:
        _raise_person_unsaved()
    try:
        return Person.objects.get(pk=person_id)
    except Person.DoesNotExist:
        _raise_person_unsaved()


def _get_lifecycle_permissions(
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[bool, bool]:
    if not actor.is_authenticated:
        return False, False

    user_model = get_user_model()
    current_actor = user_model._default_manager.get(pk=actor.pk)
    if not current_actor.is_active:
        return False, False
    if current_actor.is_superuser:
        return True, True
    return (
        current_actor.has_perm(_VIEW_ARCHIVED_PERSON_PERMISSION),
        current_actor.has_perm(_VIEW_DELETED_PERSON_PERMISSION),
    )


def _is_person_visible(
    person: Person,
    *,
    visibility_by_access_level: dict[str, bool],
    can_view_archived_person: bool,
    can_view_deleted_person: bool,
) -> bool:
    return (
        visibility_by_access_level.get(person.access_level, False)
        and (
            person.archived_at is None
            or can_view_archived_person
        )
        and (
            person.deleted_at is None
            or can_view_deleted_person
        )
    )


def _visible_biological_sibling_ids(
    *,
    person: Person,
    sibling_ids: set[int],
    visibility_by_access_level: dict[str, bool],
    can_view_archived_person: bool,
) -> set[int]:
    if not sibling_ids:
        return set()

    child_ids = sibling_ids | {person.pk}
    visible_parent_ids_by_child: dict[int, set[int]] = {}
    parent_relationships = Relationship.objects.filter(
        deleted_at__isnull=True,
        relationship_type__code="biological_parent",
        person_b_id__in=child_ids,
    ).select_related(
        "relationship_type",
        "person_a",
        "person_b",
    )
    for relationship in parent_relationships:
        parent = relationship.person_a
        if (
            not visibility_by_access_level.get(
                relationship.access_level,
                False,
            )
            or parent.deleted_at is not None
            or not _is_person_visible(
                parent,
                visibility_by_access_level=visibility_by_access_level,
                can_view_archived_person=can_view_archived_person,
                can_view_deleted_person=False,
            )
        ):
            continue
        visible_parent_ids_by_child.setdefault(
            relationship.person_b_id,
            set(),
        ).add(parent.pk)

    input_parent_ids = visible_parent_ids_by_child.get(person.pk, set())
    return {
        sibling_id
        for sibling_id in sibling_ids
        if input_parent_ids
        & visible_parent_ids_by_child.get(sibling_id, set())
    }


def get_visible_relationship_overview(
    *,
    person: Person,
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[RelationshipOverviewItem, ...]:
    """Vrať přehled vztahů bezpečně filtrovaný pro aktuálního actora."""

    visibility_by_access_level = {
        access_level: can_view_access_level(
            actor=actor,
            access_level=access_level,
        )
        for access_level in _ACCESS_LEVELS
    }
    (
        can_view_archived_person,
        can_view_deleted_person,
    ) = _get_lifecycle_permissions(actor)

    current_person = _load_current_person(person)
    if not _is_person_visible(
        current_person,
        visibility_by_access_level=visibility_by_access_level,
        can_view_archived_person=can_view_archived_person,
        can_view_deleted_person=can_view_deleted_person,
    ):
        raise PermissionDenied(
            "Nemáte oprávnění zobrazit tuto osobu."
        )

    permissionless_items = get_relationship_overview(person=current_person)
    relationship_ids = {
        relationship_id
        for item in permissionless_items
        for reason in item.reasons
        for relationship_id in reason.relationship_ids
    }
    visible_relationship_ids = set(
        Relationship.objects.filter(
            pk__in=relationship_ids,
            deleted_at__isnull=True,
            access_level__in=(
                access_level
                for access_level, is_visible
                in visibility_by_access_level.items()
                if is_visible
            ),
        ).values_list("pk", flat=True)
    )

    visible_items = tuple(
        item
        for item in permissionless_items
        if item.person.deleted_at is None
        and _is_person_visible(
            item.person,
            visibility_by_access_level=visibility_by_access_level,
            can_view_archived_person=can_view_archived_person,
            can_view_deleted_person=False,
        )
    )
    biological_sibling_ids = {
        item.person.pk
        for item in visible_items
        if any(
            reason.is_derived
            and reason.category == "sibling"
            and reason.relationship_code == "biological"
            for reason in item.reasons
        )
    }
    visible_biological_sibling_ids = _visible_biological_sibling_ids(
        person=current_person,
        sibling_ids=biological_sibling_ids,
        visibility_by_access_level=visibility_by_access_level,
        can_view_archived_person=can_view_archived_person,
    )

    result = []
    for item in visible_items:
        reasons = []
        for reason in item.reasons:
            if reason.is_derived:
                if (
                    reason.category == "sibling"
                    and reason.relationship_code == "biological"
                    and item.person.pk
                    in visible_biological_sibling_ids
                ):
                    reasons.append(reason)
                continue

            filtered_relationship_ids = tuple(
                relationship_id
                for relationship_id in reason.relationship_ids
                if relationship_id in visible_relationship_ids
            )
            if not filtered_relationship_ids:
                continue
            reasons.append(
                RelationshipOverviewReason(
                    category=reason.category,
                    relationship_code=reason.relationship_code,
                    label=reason.label,
                    relationship_ids=filtered_relationship_ids,
                    is_derived=False,
                )
            )

        if reasons:
            result.append(
                RelationshipOverviewItem(
                    person=item.person,
                    reasons=tuple(reasons),
                )
            )

    return tuple(result)
