"""Validace a odvozování technických hodnot neúplných dat."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError

from .choices import DatePrecision, DateQualifier


@dataclass(frozen=True, slots=True)
class PartialDateValue:
    """Hodnoty potřebné pro validaci a řazení neúplného data."""

    date_precision: str
    date_qualifier: str
    start_year: int | None = None
    start_month: int | None = None
    start_day: int | None = None
    end_year: int | None = None
    end_month: int | None = None
    end_day: int | None = None


ErrorMap = dict[str, list[ValidationError]]


def _add_error(
    errors: ErrorMap,
    field: str,
    message: str,
    code: str,
) -> None:
    errors.setdefault(field, []).append(ValidationError(message, code=code))


def _validate_date_parts(
    value: PartialDateValue,
    prefix: str,
    errors: ErrorMap,
) -> None:
    year = getattr(value, f"{prefix}_year")
    month = getattr(value, f"{prefix}_month")
    day = getattr(value, f"{prefix}_day")
    year_field = f"{prefix}_year"
    month_field = f"{prefix}_month"
    day_field = f"{prefix}_day"

    if month is not None and year is None:
        _add_error(
            errors,
            month_field,
            "Měsíc nelze zadat bez roku.",
            "missing_year",
        )
    if day is not None and month is None:
        _add_error(
            errors,
            day_field,
            "Den nelze zadat bez měsíce.",
            "missing_month",
        )
    if day is not None and year is None:
        _add_error(
            errors,
            day_field,
            "Den nelze zadat bez roku.",
            "missing_year",
        )

    year_is_valid = year is None or 1 <= year <= 9999
    month_is_valid = month is None or 1 <= month <= 12

    if not year_is_valid:
        _add_error(
            errors,
            year_field,
            "Rok musí být v rozsahu 1 až 9999.",
            "invalid_year",
        )
    if not month_is_valid:
        _add_error(
            errors,
            month_field,
            "Měsíc musí být v rozsahu 1 až 12.",
            "invalid_month",
        )

    if (
        year is not None
        and month is not None
        and day is not None
        and year_is_valid
        and month_is_valid
    ):
        try:
            date(year, month, day)
        except ValueError:
            _add_error(
                errors,
                day_field,
                "Den neexistuje v zadaném měsíci a roce.",
                "invalid_date",
            )


def _require_component(
    value: PartialDateValue,
    field: str,
    errors: ErrorMap,
    code: str,
    message: str,
) -> None:
    if getattr(value, field) is None:
        _add_error(errors, field, message, code)


def _reject_components(
    value: PartialDateValue,
    fields: tuple[str, ...],
    errors: ErrorMap,
) -> None:
    for field in fields:
        if getattr(value, field) is not None:
            _add_error(
                errors,
                field,
                "Tato část data neodpovídá zvolené přesnosti.",
                "unexpected_component",
            )


def _validate_precision(value: PartialDateValue, errors: ErrorMap) -> None:
    end_fields = ("end_year", "end_month", "end_day")

    if value.date_precision == DatePrecision.EXACT:
        _require_component(
            value,
            "start_year",
            errors,
            "missing_year",
            "Pro přesné datum je vyžadován rok.",
        )
        _require_component(
            value,
            "start_month",
            errors,
            "missing_month",
            "Pro přesné datum je vyžadován měsíc.",
        )
        _require_component(
            value,
            "start_day",
            errors,
            "missing_day",
            "Pro přesné datum je vyžadován den.",
        )
        _reject_components(value, end_fields, errors)
    elif value.date_precision == DatePrecision.MONTH:
        _require_component(
            value,
            "start_year",
            errors,
            "missing_year",
            "Pro měsíc a rok je vyžadován rok.",
        )
        _require_component(
            value,
            "start_month",
            errors,
            "missing_month",
            "Pro měsíc a rok je vyžadován měsíc.",
        )
        _reject_components(value, ("start_day", *end_fields), errors)
    elif value.date_precision == DatePrecision.YEAR:
        _require_component(
            value,
            "start_year",
            errors,
            "missing_year",
            "Pro rok je vyžadován rok.",
        )
        _reject_components(
            value,
            ("start_month", "start_day", *end_fields),
            errors,
        )
    elif value.date_precision == DatePrecision.RANGE:
        _require_component(
            value,
            "start_year",
            errors,
            "missing_range_start",
            "Rozmezí musí mít začátek.",
        )
        _require_component(
            value,
            "end_year",
            errors,
            "missing_range_end",
            "Rozmezí musí mít konec.",
        )
    elif value.date_precision == DatePrecision.UNKNOWN:
        _reject_components(
            value,
            (
                "start_year",
                "start_month",
                "start_day",
                "end_year",
                "end_month",
                "end_day",
            ),
            errors,
        )
    else:
        _add_error(
            errors,
            "date_precision",
            "Neznámá přesnost data.",
            "invalid_precision",
        )


def _validate_qualifier(value: PartialDateValue, errors: ErrorMap) -> None:
    allowed_precisions = {
        DateQualifier.NONE: set(DatePrecision.values),
        DateQualifier.APPROXIMATE: {
            DatePrecision.EXACT,
            DatePrecision.MONTH,
            DatePrecision.YEAR,
            DatePrecision.RANGE,
        },
        DateQualifier.BEFORE: {
            DatePrecision.EXACT,
            DatePrecision.MONTH,
            DatePrecision.YEAR,
        },
        DateQualifier.AFTER: {
            DatePrecision.EXACT,
            DatePrecision.MONTH,
            DatePrecision.YEAR,
        },
    }
    allowed = allowed_precisions.get(value.date_qualifier)

    if allowed is None or value.date_precision not in allowed:
        _add_error(
            errors,
            "date_qualifier",
            "Kvalifikátor není pro zvolenou přesnost povolen.",
            "invalid_qualifier",
        )


def _earliest_date(
    year: int | None,
    month: int | None,
    day: int | None,
) -> date | None:
    if year is None:
        return None
    return date(year, month or 1, day or 1)


def _latest_date(
    year: int | None,
    month: int | None,
    day: int | None,
) -> date | None:
    if year is None:
        return None
    if day is not None:
        return date(year, month or 1, day)
    if month is not None:
        return date(year, month, monthrange(year, month)[1])
    return date(year, 12, 31)


def derive_sort_dates(
    value: PartialDateValue,
) -> tuple[date | None, date | None]:
    """Odvoď technické meze pro řazení z validní hodnoty."""

    if value.date_precision == DatePrecision.EXACT:
        if None in (value.start_year, value.start_month, value.start_day):
            return None, None
        exact_date = date(
            value.start_year,
            value.start_month,
            value.start_day,
        )
        return exact_date, exact_date
    if value.date_precision == DatePrecision.MONTH:
        if value.start_year is None or value.start_month is None:
            return None, None
        return (
            date(value.start_year, value.start_month, 1),
            date(
                value.start_year,
                value.start_month,
                monthrange(value.start_year, value.start_month)[1],
            ),
        )
    if value.date_precision == DatePrecision.YEAR:
        if value.start_year is None:
            return None, None
        return date(value.start_year, 1, 1), date(value.start_year, 12, 31)
    if value.date_precision == DatePrecision.RANGE:
        return (
            _earliest_date(
                value.start_year,
                value.start_month,
                value.start_day,
            ),
            _latest_date(
                value.end_year,
                value.end_month,
                value.end_day,
            ),
        )
    if value.date_precision == DatePrecision.UNKNOWN:
        return None, None
    raise ValueError(f"Neznámá přesnost data: {value.date_precision!r}")


def validate_partial_date(value: PartialDateValue) -> None:
    """Ověř strukturu, kalendářní platnost, přesnost a kvalifikátor."""

    errors: ErrorMap = {}
    _validate_date_parts(value, "start", errors)
    _validate_date_parts(value, "end", errors)
    _validate_precision(value, errors)
    _validate_qualifier(value, errors)

    component_fields = {
        "start_year",
        "start_month",
        "start_day",
        "end_year",
        "end_month",
        "end_day",
    }
    if (
        value.date_precision == DatePrecision.RANGE
        and not component_fields.intersection(errors)
    ):
        start, end = derive_sort_dates(value)
        if start is not None and end is not None and end < start:
            _add_error(
                errors,
                "end_year",
                "Konec rozmezí nesmí být před začátkem.",
                "range_end_before_start",
            )

    if errors:
        raise ValidationError(errors)
