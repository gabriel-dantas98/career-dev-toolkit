from __future__ import annotations

import calendar
import re
from dataclasses import dataclass

_MONTH_ALIASES: dict[str, int] = {
    "jan": 1,
    "fev": 2,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "apr": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "aug": 8,
    "set": 9,
    "sep": 9,
    "out": 10,
    "oct": 10,
    "nov": 11,
    "dez": 12,
    "dec": 12,
}

_QUARTER_BOUNDS: dict[int, tuple[int, int]] = {
    1: (1, 3),
    2: (4, 6),
    3: (7, 9),
    4: (10, 12),
}


@dataclass(frozen=True)
class Period:
    raw_value: str
    iso_bounds: tuple[str, str]
    precision: str
    reference_year: int


def _iso_date(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def _month_end(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _parse_month_token(token: str) -> int | None:
    cleaned = token.strip().lower()
    if not cleaned:
        return None
    if cleaned.isdigit():
        month = int(cleaned)
        return month if 1 <= month <= 12 else None
    return _MONTH_ALIASES.get(cleaned[:3])


def _parse_pt_br_day(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", value.strip())
    if not match:
        return None
    day, month, year = (int(part) for part in match.groups())
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    iso = _iso_date(year, month, day)
    return iso, iso


def _parse_quarter(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"Q([1-4])\s+(\d{4})", value.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    quarter = int(match.group(1))
    year = int(match.group(2))
    start_month, end_month = _QUARTER_BOUNDS[quarter]
    return (
        _iso_date(year, start_month, 1),
        _iso_date(year, end_month, _month_end(year, end_month)),
    )


def _parse_month_year(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"([A-Za-z]{3,})\s+(\d{4})", value.strip())
    if not match:
        return None
    month = _parse_month_token(match.group(1))
    if month is None:
        return None
    year = int(match.group(2))
    return (
        _iso_date(year, month, 1),
        _iso_date(year, month, _month_end(year, month)),
    )


def _parse_yearless_range(value: str, reference_year: int) -> tuple[str, str, str] | None:
    normalized = value.strip().replace("–", "-")
    if "-" not in normalized:
        return None
    start_token, end_token = normalized.split("-", 1)
    start_month = _parse_month_token(start_token)
    end_month = _parse_month_token(end_token)
    if start_month is None or end_month is None:
        return None
    return (
        _iso_date(reference_year, start_month, 1),
        _iso_date(reference_year, end_month, _month_end(reference_year, end_month)),
        "range",
    )


def _parse_open_end_range(value: str, reference_year: int) -> tuple[str, str, str] | None:
    normalized = value.strip().replace("–", "-")
    if not normalized.startswith("-"):
        return None
    end_month = _parse_month_token(normalized[1:])
    if end_month is None:
        return None
    return (
        _iso_date(reference_year, 1, 1),
        _iso_date(reference_year, end_month, _month_end(reference_year, end_month)),
        "range",
    )


def parse_period(value: str, *, reference_year: int) -> Period:
    stripped = value.strip()

    day_bounds = _parse_pt_br_day(stripped)
    if day_bounds is not None:
        return Period(stripped, day_bounds, "day", reference_year)

    quarter_bounds = _parse_quarter(stripped)
    if quarter_bounds is not None:
        return Period(stripped, quarter_bounds, "quarter", reference_year)

    month_bounds = _parse_month_year(stripped)
    if month_bounds is not None:
        return Period(stripped, month_bounds, "month", reference_year)

    open_range = _parse_open_end_range(stripped, reference_year)
    if open_range is not None:
        start, end, precision = open_range
        return Period(stripped, (start, end), precision, reference_year)

    yearless_range = _parse_yearless_range(stripped, reference_year)
    if yearless_range is not None:
        start, end, precision = yearless_range
        return Period(stripped, (start, end), precision, reference_year)

    raise ValueError(f"unsupported period value: {value!r}")


def quarters_for(period: Period) -> tuple[str, ...]:
    start_year = int(period.iso_bounds[0][:4])
    end_year = int(period.iso_bounds[1][:4])
    start_month = int(period.iso_bounds[0][5:7])
    end_month = int(period.iso_bounds[1][5:7])

    quarters: list[str] = []
    for year in range(start_year, end_year + 1):
        for quarter, (quarter_start, quarter_end) in _QUARTER_BOUNDS.items():
            if year == start_year and quarter_end < start_month:
                continue
            if year == end_year and quarter_start > end_month:
                continue
            quarters.append(f"Q{quarter} {year}")
    return tuple(quarters)


def sort_start(period: Period) -> str:
    start = period.iso_bounds[0]
    if period.raw_value.strip().replace("–", "-").startswith("-"):
        return _iso_date(period.reference_year, 1, 1)
    return start
