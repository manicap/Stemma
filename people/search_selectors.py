"""Actor-aware searching, filtering and ordering for the person browser."""

from dataclasses import dataclass
from datetime import date
import unicodedata

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from common.choices import AccessLevel
from common.permissions import can_view_access_level

from .derived_selectors import (
    PersonPresentation,
    get_visible_person_presentations,
)
from .models import PersonCategory, PersonName

DEFAULT_PERSON_SORT = "youngest"
PERSON_SORT_CHOICES = (
    (DEFAULT_PERSON_SORT, "Od nejmladších"),
    ("oldest", "Od nejstarších"),
    ("last_name_asc", "Příjmení A–Z"),
    ("last_name_desc", "Příjmení Z–A"),
    ("first_name_asc", "Jméno A–Z"),
    ("first_name_desc", "Jméno Z–A"),
)
PERSON_SUGGESTION_LIMIT = 8
PERSON_SEARCH_QUERY_MAX_LENGTH = 200


@dataclass(frozen=True, slots=True)
class PersonBrowserResult:
    """One safe browser state derived only from actor-visible records."""

    visible_presentations: tuple[PersonPresentation, ...]
    presentations: tuple[PersonPresentation, ...]
    suggestions: tuple[PersonPresentation, ...]
    categories: tuple[PersonCategory, ...]
    query: str
    category_id: int | None
    sort: str


def normalize_person_search_text(value: object) -> str:
    """Return a casefolded, diacritic-free value with stable whitespace."""

    decomposed = unicodedata.normalize("NFKD", str(value or ""))
    without_marks = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_marks.casefold().split())


def _visible_access_levels(
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[str, ...]:
    return tuple(
        access_level
        for access_level in AccessLevel.values
        if can_view_access_level(actor=actor, access_level=access_level)
    )


def _visible_alternative_names(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    person_ids: tuple[int, ...],
) -> dict[int, tuple[str, ...]]:
    values_by_person: dict[int, list[str]] = {
        person_id: [] for person_id in person_ids
    }
    if not person_ids:
        return {}

    names = PersonName.objects.filter(
        person_id__in=person_ids,
        access_level__in=_visible_access_levels(actor),
        archived_at__isnull=True,
        deleted_at__isnull=True,
    ).values_list("person_id", "value", "normalized_value")
    for person_id, value, normalized_value in names:
        values_by_person[person_id].extend((value, normalized_value))
    return {
        person_id: tuple(values)
        for person_id, values in values_by_person.items()
    }


def _categories_for_visible_people(
    presentations: tuple[PersonPresentation, ...],
) -> tuple[PersonCategory, ...]:
    assigned_category_ids = {
        presentation.person.category_id
        for presentation in presentations
        if presentation.person.category_id is not None
    }
    return tuple(
        PersonCategory.objects.filter(
            Q(is_active=True) | Q(pk__in=assigned_category_ids)
        )
    )


def _birth_key(
    presentation: PersonPresentation,
    *,
    youngest_first: bool,
) -> tuple[object, ...]:
    start = presentation.facts.birth_sort_date
    end = presentation.facts.birth_sort_date_end
    person = presentation.person
    if start is None:
        return (
            1,
            0,
            0,
            normalize_person_search_text(person.last_name),
            normalize_person_search_text(person.first_name),
            person.pk,
        )
    end = end or start
    direction = -1 if youngest_first else 1
    return (
        0,
        direction * start.toordinal(),
        direction * end.toordinal(),
        normalize_person_search_text(person.last_name),
        normalize_person_search_text(person.first_name),
        person.pk,
    )


def _name_key(
    presentation: PersonPresentation,
    *,
    primary: str,
) -> tuple[object, ...]:
    person = presentation.person
    primary_value = normalize_person_search_text(getattr(person, primary))
    secondary_field = "first_name" if primary == "last_name" else "last_name"
    secondary_value = normalize_person_search_text(
        getattr(person, secondary_field)
    )
    return (
        not bool(primary_value),
        primary_value,
        secondary_value,
        person.pk,
    )


def _sort_presentations(
    presentations: tuple[PersonPresentation, ...],
    sort: str,
) -> tuple[PersonPresentation, ...]:
    if sort == "oldest":
        return tuple(
            sorted(
                presentations,
                key=lambda item: _birth_key(item, youngest_first=False),
            )
        )
    if sort in {"last_name_asc", "last_name_desc"}:
        known = tuple(
            item for item in presentations if item.person.last_name.strip()
        )
        unknown = tuple(
            item for item in presentations if not item.person.last_name.strip()
        )
        return tuple(
            sorted(
                known,
                key=lambda item: _name_key(item, primary="last_name"),
                reverse=sort.endswith("desc"),
            )
        ) + tuple(sorted(unknown, key=lambda item: item.person.pk))
    if sort in {"first_name_asc", "first_name_desc"}:
        known = tuple(
            item for item in presentations if item.person.first_name.strip()
        )
        unknown = tuple(
            item for item in presentations if not item.person.first_name.strip()
        )
        return tuple(
            sorted(
                known,
                key=lambda item: _name_key(item, primary="first_name"),
                reverse=sort.endswith("desc"),
            )
        ) + tuple(sorted(unknown, key=lambda item: item.person.pk))
    return tuple(
        sorted(
            presentations,
            key=lambda item: _birth_key(item, youngest_first=True),
        )
    )


def _matches_query(
    presentation: PersonPresentation,
    *,
    query_tokens: tuple[str, ...],
    alternative_names: dict[int, tuple[str, ...]],
) -> bool:
    if not query_tokens:
        return True
    person = presentation.person
    values = (
        person.first_name,
        person.last_name,
        f"{person.first_name} {person.last_name}",
        f"{person.last_name} {person.first_name}",
        presentation.facts.birth_text or "",
        *alternative_names.get(person.pk, ()),
    )
    normalized_values = tuple(normalize_person_search_text(value) for value in values)
    return all(
        any(token in value for value in normalized_values)
        for token in query_tokens
    )


def _suggestion_rank(
    presentation: PersonPresentation,
    *,
    normalized_query: str,
    alternative_names: dict[int, tuple[str, ...]],
) -> tuple[object, ...]:
    person = presentation.person
    values = tuple(
        normalize_person_search_text(value)
        for value in (
            f"{person.first_name} {person.last_name}",
            f"{person.last_name} {person.first_name}",
            person.first_name,
            person.last_name,
            *alternative_names.get(person.pk, ()),
        )
    )
    if normalized_query in values:
        rank = 0
    elif any(value.startswith(normalized_query) for value in values):
        rank = 1
    else:
        rank = 2
    return (
        rank,
        normalize_person_search_text(person.last_name),
        normalize_person_search_text(person.first_name),
        person.pk,
    )


def get_visible_person_browser(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    query: str = "",
    category: str = "",
    sort: str = DEFAULT_PERSON_SORT,
    suggestion_limit: int = PERSON_SUGGESTION_LIMIT,
) -> PersonBrowserResult:
    """Return one authorized, combined person-list and suggestion state."""

    visible_presentations = get_visible_person_presentations(actor=actor)
    categories = _categories_for_visible_people(visible_presentations)
    valid_category_ids = {item.pk for item in categories}
    try:
        parsed_category_id = int(category) if category else None
    except (TypeError, ValueError):
        parsed_category_id = None
    category_id = (
        parsed_category_id
        if parsed_category_id in valid_category_ids
        else None
    )
    valid_sorts = {value for value, _label in PERSON_SORT_CHOICES}
    selected_sort = sort if sort in valid_sorts else DEFAULT_PERSON_SORT
    bounded_query = str(query or "")[:PERSON_SEARCH_QUERY_MAX_LENGTH].strip()
    normalized_query = normalize_person_search_text(bounded_query)
    query_tokens = tuple(normalized_query.split())
    person_ids = tuple(
        presentation.person.pk for presentation in visible_presentations
    )
    alternative_names = _visible_alternative_names(
        actor=actor,
        person_ids=person_ids,
    )

    filtered = tuple(
        presentation
        for presentation in visible_presentations
        if (
            category_id is None
            or presentation.person.category_id == category_id
        )
        and _matches_query(
            presentation,
            query_tokens=query_tokens,
            alternative_names=alternative_names,
        )
    )
    ordered = _sort_presentations(filtered, selected_sort)
    suggestions = (
        tuple(
            sorted(
                ordered,
                key=lambda item: _suggestion_rank(
                    item,
                    normalized_query=normalized_query,
                    alternative_names=alternative_names,
                ),
            )[: max(suggestion_limit, 0)]
        )
        if normalized_query
        else ()
    )
    return PersonBrowserResult(
        visible_presentations=visible_presentations,
        presentations=ordered,
        suggestions=suggestions,
        categories=categories,
        query=bounded_query,
        category_id=category_id,
        sort=selected_sort,
    )
