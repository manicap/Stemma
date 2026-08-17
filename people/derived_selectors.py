from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from common.choices import AccessLevel, DatePrecision, DateQualifier
from common.permissions import can_view_access_level
from events.models import Event, EventParticipant

from .models import Person
from .selectors import get_visible_people

__all__ = (
    "PersonDerivedFacts",
    "PersonPresentation",
    "get_visible_person_presentations",
)

_LIFE_EVENT_ROLES = {
    "birth": "born_person",
    "death": "deceased_person",
}


@dataclass(frozen=True, slots=True)
class PersonDerivedFacts:
    """Actor-specific presentation facts derived from visible sources."""

    birth_text: str | None
    death_text: str | None
    is_deceased: bool
    age: int | None
    age_text: str | None
    roman_suffix: str | None


@dataclass(frozen=True, slots=True)
class PersonPresentation:
    """Visible person paired with derived facts for one actor."""

    person: Person
    facts: PersonDerivedFacts


def _visible_access_levels(
    actor: AbstractBaseUser | AnonymousUser,
) -> tuple[str, ...]:
    return tuple(
        access_level
        for access_level in AccessLevel.values
        if can_view_access_level(actor=actor, access_level=access_level)
    )


def _life_events_by_person(
    *,
    people: Iterable[Person],
    actor: AbstractBaseUser | AnonymousUser,
) -> dict[int, dict[str, list[Event]]]:
    person_ids = tuple(person.pk for person in people)
    grouped: dict[int, dict[str, list[Event]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not person_ids:
        return grouped

    participations = EventParticipant.objects.filter(
        person_id__in=person_ids,
        event__event_type__code__in=_LIFE_EVENT_ROLES,
        role__code__in=_LIFE_EVENT_ROLES.values(),
        event__access_level__in=_visible_access_levels(actor),
        event__archived_at__isnull=True,
        event__deleted_at__isnull=True,
    ).select_related("event", "event__event_type", "role")
    for participation in participations:
        event_code = participation.event.event_type.code
        if participation.role.code != _LIFE_EVENT_ROLES[event_code]:
            continue
        grouped[participation.person_id][event_code].append(
            participation.event
        )
    return grouped


def _format_date_parts(
    year: int | None,
    month: int | None,
    day: int | None,
) -> str | None:
    if year is None:
        return None
    if month is None:
        return str(year)
    if day is None:
        return f"{month}/{year}"
    return f"{day}. {month}. {year}"


def _format_partial_date(event: Event | None) -> str | None:
    if event is None or event.date_precision == DatePrecision.UNKNOWN:
        return None
    if event.date_precision == DatePrecision.RANGE:
        start = _format_date_parts(
            event.start_year,
            event.start_month,
            event.start_day,
        )
        end = _format_date_parts(
            event.end_year,
            event.end_month,
            event.end_day,
        )
        value = f"{start}–{end}" if start and end else start or end
    else:
        value = _format_date_parts(
            event.start_year,
            event.start_month,
            event.start_day,
        )
    if value is None:
        return None
    prefix = {
        DateQualifier.NONE: "",
        DateQualifier.APPROXIMATE: "asi ",
        DateQualifier.BEFORE: "před ",
        DateQualifier.AFTER: "po ",
    }[event.date_qualifier]
    return f"{prefix}{value}"


def _age_on(birth: date, reference: date) -> int:
    return reference.year - birth.year - (
        (reference.month, reference.day) < (birth.month, birth.day)
    )


def _reliable_age(
    *,
    birth: Event | None,
    reference: Event | None,
    as_of: date,
    is_deceased: bool,
) -> int | None:
    if birth is None or birth.date_qualifier != DateQualifier.NONE:
        return None
    if birth.sort_date is None or birth.sort_date_end is None:
        return None
    if is_deceased:
        if reference is None or reference.date_qualifier != DateQualifier.NONE:
            return None
        reference_start = reference.sort_date
        reference_end = reference.sort_date_end
    else:
        reference_start = reference_end = as_of
    if reference_start is None or reference_end is None:
        return None

    youngest_age = _age_on(birth.sort_date_end, reference_start)
    oldest_age = _age_on(birth.sort_date, reference_end)
    if youngest_age < 0 or youngest_age != oldest_age:
        return None
    return youngest_age


def _format_age(age: int | None) -> str | None:
    if age is None:
        return None
    if age == 1:
        unit = "rok"
    elif age % 10 in (2, 3, 4) and age % 100 not in (12, 13, 14):
        unit = "roky"
    else:
        unit = "let"
    return f"{age} {unit}"


def _to_roman(value: int) -> str:
    parts = []
    for number, numeral in (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ):
        count, value = divmod(value, number)
        parts.append(numeral * count)
    return "".join(parts)


def _roman_suffixes(
    *,
    people: tuple[Person, ...],
    unique_births: dict[int, Event | None],
) -> dict[int, str | None]:
    cohorts: dict[tuple[str, str], list[Person]] = defaultdict(list)
    for person in people:
        cohorts[(person.first_name, person.last_name)].append(person)

    suffixes: dict[int, str | None] = {person.pk: None for person in people}
    for cohort in cohorts.values():
        if len(cohort) < 2:
            continue
        ordered = sorted(
            cohort,
            key=lambda person: (
                unique_births[person.pk] is None
                or unique_births[person.pk].sort_date is None,
                (
                    unique_births[person.pk].sort_date
                    if unique_births[person.pk] is not None
                    and unique_births[person.pk].sort_date is not None
                    else date.max
                ),
                (
                    unique_births[person.pk].sort_date_end
                    if unique_births[person.pk] is not None
                    and unique_births[person.pk].sort_date_end is not None
                    else date.max
                ),
                person.pk,
            ),
        )
        for position, person in enumerate(ordered, start=1):
            suffixes[person.pk] = f"{_to_roman(position)}."
    return suffixes


def get_visible_person_presentations(
    *,
    actor: AbstractBaseUser | AnonymousUser,
    as_of: date | None = None,
) -> tuple[PersonPresentation, ...]:
    """Return visible people and facts derived only from visible sources."""

    people = tuple(get_visible_people(actor=actor))
    life_events = _life_events_by_person(people=people, actor=actor)
    unique_births = {
        person.pk: (
            life_events[person.pk]["birth"][0]
            if len(life_events[person.pk]["birth"]) == 1
            else None
        )
        for person in people
    }
    unique_deaths = {
        person.pk: (
            life_events[person.pk]["death"][0]
            if len(life_events[person.pk]["death"]) == 1
            else None
        )
        for person in people
    }
    suffixes = _roman_suffixes(
        people=people,
        unique_births=unique_births,
    )
    reference_date = as_of or timezone.localdate()

    result = []
    for person in people:
        birth = unique_births[person.pk]
        death = unique_deaths[person.pk]
        is_deceased = bool(life_events[person.pk]["death"])
        age = _reliable_age(
            birth=birth,
            reference=death,
            as_of=reference_date,
            is_deceased=is_deceased,
        )
        result.append(
            PersonPresentation(
                person=person,
                facts=PersonDerivedFacts(
                    birth_text=_format_partial_date(birth),
                    death_text=_format_partial_date(death),
                    is_deceased=is_deceased,
                    age=age,
                    age_text=_format_age(age),
                    roman_suffix=suffixes[person.pk],
                ),
            )
        )
    return tuple(result)
