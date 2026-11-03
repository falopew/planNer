"""Pure overlap tests: half-open boundaries, stable pairs and occurrence identity."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from src.engine.conflicts import detect_conflicts
from src.models.event import Event
from src.models.reminder import Reminder

START = datetime(2026, 11, 4)
END = START + timedelta(days=1)


def event(identifier: int, start: int, end: int) -> Event:
    return Event(
        id=identifier,
        title=f"Event {identifier}",
        start_datetime=START + timedelta(hours=start),
        end_datetime=START + timedelta(hours=end),
        created_at=START,
        updated_at=START,
    )


@pytest.mark.parametrize(
    ("a", "b", "overlap"),
    [
        ((9, 11), (10, 12), (10, 11)),
        ((9, 12), (10, 11), (10, 11)),
        ((9, 11), (9, 11), (9, 11)),
        ((9, 10), (10, 11), None),
        ((9, 10), (11, 12), None),
        ((-2, 1), (-1, 2), (0, 1)),
        ((23, 26), (22, 25), (23, 24)),
        ((-2, 0), (-1, 2), None),
        ((23, 26), (24, 27), None),
    ],
)
def test_overlap_cases(a: tuple, b: tuple, overlap: tuple | None) -> None:
    first, second = event(1, *a), event(2, *b)
    result = detect_conflicts([first, second], START, END)
    assert len(result) == (0 if overlap is None else 1)
    if overlap:
        assert (result[0].overlap_start, result[0].overlap_end) == tuple(
            START + timedelta(hours=value) for value in overlap
        )
    assert detect_conflicts([second, first], START, END) == result


def test_reminders_empty_single_and_duplicate_occurrences() -> None:
    first, second = event(1, 9, 12), event(2, 10, 11)
    reminder = Reminder(
        id=1,
        title="Bell",
        reminder_datetime=START + timedelta(hours=10),
        created_at=START,
        updated_at=START,
    )
    assert detect_conflicts([], START, END) == []
    assert detect_conflicts([first, first, reminder], START, END) == []
    assert (
        len(detect_conflicts([first, second, first, second, reminder], START, END)) == 1
    )


def test_three_way_overlap_reports_all_pairs_without_mutation() -> None:
    items = [event(3, 10, 12), event(1, 9, 13), event(2, 10, 11)]
    before = list(items)
    result = detect_conflicts(items, START, END)
    assert [(pair.first.id, pair.second.id) for pair in result] == [
        (1, 2),
        (1, 3),
        (2, 3),
    ]
    assert items == before


def test_distinct_occurrences_of_same_series_can_conflict() -> None:
    first = event(1, -1, 25)
    second = replace(
        first,
        start_datetime=START + timedelta(hours=23),
        end_datetime=START + timedelta(hours=49),
    )
    result = detect_conflicts([first, second], START, END)
    assert len(result) == 1
    assert result[0].first.id == result[0].second.id
    assert result[0].first.start_datetime != result[0].second.start_datetime


def test_overlap_outside_selected_window_is_not_reported() -> None:
    assert detect_conflicts([event(1, -5, 1), event(2, -4, -1)], START, END) == []


@pytest.mark.parametrize("end", [START, START - timedelta(seconds=1)])
def test_invalid_window(end: datetime) -> None:
    with pytest.raises(ValueError):
        detect_conflicts([], START, end)
