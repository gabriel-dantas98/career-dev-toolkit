import pytest

from careeros.dates import parse_period, quarters_for, sort_start


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("jan–mar", ("2026-01-01", "2026-03-31")),
        ("03/04/2026", ("2026-04-03", "2026-04-03")),
        ("Q2 2026", ("2026-04-01", "2026-06-30")),
    ],
)
def test_periods_parse_pt_br(value: str, expected: tuple[str, str]) -> None:
    assert parse_period(value, reference_year=2026).iso_bounds == expected


@pytest.mark.parametrize(
    ("value", "precision"),
    [
        ("03/04/2026", "day"),
        ("mar 2026", "month"),
        ("Q2 2026", "quarter"),
        ("jan–mar", "range"),
    ],
)
def test_period_precision(value: str, precision: str) -> None:
    assert parse_period(value, reference_year=2026).precision == precision


def test_yearless_period_uses_reference_year() -> None:
    period = parse_period("ago–out", reference_year=2025)
    assert period.iso_bounds == ("2025-08-01", "2025-10-31")


def test_quarters_for_single_quarter() -> None:
    period = parse_period("Q2 2026", reference_year=2026)
    assert quarters_for(period) == ("Q2 2026",)


def test_quarters_for_multi_quarter_range() -> None:
    period = parse_period("jan–jun", reference_year=2026)
    assert quarters_for(period) == ("Q1 2026", "Q2 2026")


def test_sort_start_uses_period_start() -> None:
    period = parse_period("mar 2026", reference_year=2026)
    assert sort_start(period) == "2026-03-01"


def test_sort_start_clamps_open_start_to_reference_year() -> None:
    period = parse_period("–mar", reference_year=2026)
    assert sort_start(period) == "2026-01-01"


def test_invalid_calendar_date_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported period"):
        parse_period("31/02/2026", reference_year=2026)
