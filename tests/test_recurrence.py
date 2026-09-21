"""Pure recurrence contracts, independent of SQLite and Streamlit."""

from datetime import UTC, date, datetime, timedelta

import pytest
from dateutil.rrule import rrulestr

from src.engine import recurrence
from src.engine.recurrence import (
    build_recurrence_rule,
    generate_occurrences,
    normalize_recurrence_rule,
    parse_recurrence_rule,
)
from src.models.recurrence import RecurrencePattern, RecurrenceValidationError

BASE = datetime(2026, 9, 21, 9)


@pytest.mark.parametrize(
    ("pattern", "expected_days"),
    [
        (RecurrencePattern("daily"), [21, 22, 23, 24, 25, 26, 27]),
        (RecurrencePattern("daily", interval=2), [21, 23, 25, 27]),
        (RecurrencePattern("weekly"), [21]),
        (RecurrencePattern("weekly", weekdays=(0, 2, 4)), [21, 23, 25]),
        (RecurrencePattern("weekly", weekdays=(0, 1, 2, 3, 4)), [21, 22, 23, 24, 25]),
    ],
)
def test_week_patterns(pattern: RecurrencePattern, expected_days: list[int]) -> None:
    rule = build_recurrence_rule(pattern, BASE)
    actual = generate_occurrences(
        BASE, rule, datetime(2026, 9, 21), datetime(2026, 9, 28)
    )
    assert actual == [datetime(2026, 9, day, 9) for day in expected_days]


def test_daily_example_and_half_open_bounds() -> None:
    rule = "FREQ=DAILY;INTERVAL=1"
    assert generate_occurrences(
        BASE, rule, datetime(2026, 9, 21), datetime(2026, 9, 24)
    ) == [BASE + timedelta(days=i) for i in range(3)]
    assert generate_occurrences(BASE, rule, BASE, BASE + timedelta(days=1)) == [BASE]


def test_weekly_and_two_week_interval() -> None:
    friday = datetime(2026, 9, 25, 19)
    for interval, offsets in [(1, [0, 7, 14, 21]), (2, [0, 14])]:
        rule = build_recurrence_rule(RecurrencePattern("weekly", interval), friday)
        assert generate_occurrences(
            friday, rule, friday, friday + timedelta(days=28)
        ) == [friday + timedelta(days=i) for i in offsets]


@pytest.mark.parametrize(
    ("day", "interval", "months"),
    [
        (1, 1, list(range(1, 13))),
        (1, 3, [1, 4, 7, 10]),
        (31, 1, [1, 3, 5, 7, 8, 10, 12]),
        (31, 3, [1, 7, 10]),
    ],
)
def test_monthly_skips_invalid_dates(
    day: int, interval: int, months: list[int]
) -> None:
    base = datetime(2026, 1, day, 9)
    rule = build_recurrence_rule(RecurrencePattern("monthly", interval), base)
    assert generate_occurrences(
        base, rule, datetime(2026, 1, 1), datetime(2027, 1, 1)
    ) == [datetime(2026, month, day, 9) for month in months]


def test_inclusive_end_date_and_anchor_exclusion() -> None:
    base = datetime(2026, 9, 23, 23, 59, 59, 123456)
    rule = build_recurrence_rule(
        RecurrencePattern("weekly", weekdays=(0,), end_date=date(2026, 11, 30)), base
    )
    assert rule == "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO;UNTIL=20261130T235959"
    values = generate_occurrences(
        base, rule, datetime(2026, 9, 1), datetime(2026, 12, 31)
    )
    assert values[0] == datetime(2026, 9, 28, 23, 59, 59, 123456)
    assert values[-1] == datetime(2026, 11, 30, 23, 59, 59, 123456)
    assert (
        generate_occurrences(base, rule, datetime(2026, 12, 1), datetime(2027, 1, 1))
        == []
    )


def test_weekdays_weekend_anchor_and_none_rule() -> None:
    saturday = datetime(2026, 9, 26, 9)
    rule = build_recurrence_rule(
        RecurrencePattern("weekly", weekdays=(0, 1, 2, 3, 4)), saturday
    )
    assert generate_occurrences(saturday, rule, saturday, datetime(2026, 9, 29)) == [
        datetime(2026, 9, 28, 9)
    ]
    assert generate_occurrences(BASE, None, BASE, BASE + timedelta(days=5)) == [BASE]
    assert (
        generate_occurrences(
            BASE, None, BASE + timedelta(days=1), BASE + timedelta(days=2)
        )
        == []
    )


def test_empty_range_and_invalid_range() -> None:
    assert generate_occurrences(BASE, "FREQ=DAILY", BASE, BASE) == []
    with pytest.raises(RecurrenceValidationError):
        generate_occurrences(BASE, "FREQ=DAILY", BASE, BASE - timedelta(seconds=1))
    with pytest.raises(RecurrenceValidationError):
        generate_occurrences(BASE, "FREQ=DAILY", BASE.replace(tzinfo=UTC), BASE)


@pytest.mark.parametrize(
    "pattern",
    [
        RecurrencePattern("daily", 0),
        RecurrencePattern("daily", -1),
        RecurrencePattern("daily", 1.5),
        RecurrencePattern("daily", True),
        RecurrencePattern("weekly", weekdays=()),
        RecurrencePattern("weekly", weekdays=(7,)),
        RecurrencePattern("daily", weekdays=(0,)),
        RecurrencePattern("yearly"),
        RecurrencePattern("daily", end_date=date(2026, 9, 20)),
    ],
)
def test_invalid_settings(pattern: RecurrencePattern) -> None:
    with pytest.raises(RecurrenceValidationError):
        build_recurrence_rule(pattern, BASE)


@pytest.mark.parametrize(
    "rule",
    [
        "",
        "broken",
        "FREQ=DAILY;COUNT=10",
        "FREQ=YEARLY",
        "FREQ=HOURLY",
        "FREQ=WEEKLY;BYDAY=",
        "FREQ=WEEKLY;BYDAY=XX",
        "FREQ=WEEKLY;BYDAY=3TU",
        "FREQ=DAILY;INTERVAL=0",
        "FREQ=DAILY;INTERVAL=-1",
        "FREQ=DAILY;INTERVAL=1.5",
        "FREQ=DAILY;UNTIL=20260230T235959",
        "FREQ=DAILY;UNTIL=20260922T235959Z",
        "FREQ=DAILY;COUNT=1;UNTIL=20260922T235959",
        "FREQ=DAILY;FREQ=WEEKLY",
        "DTSTART=20260921T090000;FREQ=DAILY",
        "FREQ=MONTHLY;BYMONTHDAY=-1",
        "FREQ=DAILY\nEXDATE:20260921T090000",
        "FREQ=DAILY;UNTIL=20260922T000000",
    ],
)
def test_unsupported_rules_rejected(rule: str) -> None:
    with pytest.raises(RecurrenceValidationError):
        parse_recurrence_rule(rule, BASE)


def test_rule_normalization_and_roundtrip() -> None:
    rule = normalize_recurrence_rule("BYDAY=FR,MO,MO,WE;FREQ=WEEKLY;INTERVAL=02", BASE)
    assert rule == "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR"
    assert build_recurrence_rule(parse_recurrence_rule(rule, BASE), BASE) == rule
    assert normalize_recurrence_rule(None, BASE) is None


@pytest.mark.parametrize(
    "pattern",
    [
        RecurrencePattern("daily", 3),
        RecurrencePattern("weekly", 2),
        RecurrencePattern("weekly", 3, (0, 2, 4)),
        RecurrencePattern("monthly", 1),
        RecurrencePattern("monthly", 3),
    ],
)
def test_window_fast_forward_matches_dateutil(pattern: RecurrencePattern) -> None:
    # Reference starts at the real DTSTART; production skips old cycles.
    base = datetime(2020, 1, 31, 19)
    rule = build_recurrence_rule(pattern, base)
    for start in [datetime(2026, 2, 1), datetime(2026, 9, 23), datetime(2027, 1, 1)]:
        end = start + timedelta(days=60)
        expected = [
            value
            for value in rrulestr(rule, dtstart=base).between(start, end, inc=True)
            if value < end
        ]
        assert generate_occurrences(base, rule, start, end) == expected


def test_old_series_is_reanchored_near_window(monkeypatch: pytest.MonkeyPatch) -> None:
    real = recurrence.rrule
    anchors = []

    def capture(*args: object, **kwargs: object) -> object:
        anchors.append(kwargs["dtstart"])
        return real(*args, **kwargs)

    monkeypatch.setattr(recurrence, "rrule", capture)
    result = generate_occurrences(
        datetime(1900, 1, 1, 9),
        "FREQ=DAILY;INTERVAL=1",
        datetime(2026, 9, 21),
        datetime(2026, 9, 28),
    )
    assert len(result) == 7
    assert anchors == [datetime(2026, 9, 21, 9)]


def test_reanchoring_with_nonmatching_weekday_and_leap_month() -> None:
    for base, pattern in [
        (datetime(2024, 2, 29, 9), RecurrencePattern("monthly", 12)),
        (datetime(2026, 9, 23, 9), RecurrencePattern("weekly", 2, (0, 4))),
    ]:
        rule = build_recurrence_rule(pattern, base)
        for year in (2027, 2028):
            lower, upper = datetime(year, 1, 1), datetime(year + 1, 1, 1)
            expected = [
                value
                for value in rrulestr(rule, dtstart=base).between(
                    lower, upper, inc=True
                )
                if value < upper
            ]
            assert generate_occurrences(base, rule, lower, upper) == expected


def test_microsecond_boundary_and_early_year_rule_roundtrip() -> None:
    base = BASE.replace(microsecond=123456)
    assert generate_occurrences(base, "FREQ=DAILY", base, base + timedelta(days=1)) == [
        base
    ]
    assert (
        generate_occurrences(
            base,
            "FREQ=DAILY",
            base.replace(microsecond=123457),
            base + timedelta(days=1),
        )
        == []
    )
    early = datetime(100, 1, 1, 9)
    rule = build_recurrence_rule(
        RecurrencePattern("daily", end_date=date(100, 1, 2)), early
    )
    assert rule.endswith("UNTIL=01000102T235959")
    assert parse_recurrence_rule(rule, early).end_date == date(100, 1, 2)
