"""Calendar selection uses real services and isolated SQLite storage."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from src.database.db import initialize_database
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import EventInput
from src.models.reminder import ReminderInput
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.services.schedule_service import ScheduleService
from src.services.validation import InputValidationError
from src.utils.time_utils import get_day_bounds, get_week_bounds, get_week_start

DAY = date(2026, 9, 21)
MIDNIGHT = datetime(2026, 9, 21)


@pytest.fixture
def services(
    tmp_path: Path,
) -> Iterator[tuple[EventService, ReminderService, ScheduleService]]:
    engine = initialize_database(tmp_path / "calendar.db")
    events = EventService(EventRepository(engine))
    reminders = ReminderService(ReminderRepository(engine))
    try:
        yield events, reminders, ScheduleService(events, reminders)
    finally:
        engine.dispose()


def test_combined_day_order_and_reminder_inside_event(services: tuple) -> None:
    events, reminders, schedule = services
    late = events.create_event(
        EventInput(
            title="Afternoon",
            start_datetime=MIDNIGHT + timedelta(hours=13),
            end_datetime=MIDNIGHT + timedelta(hours=14),
        )
    )
    early = events.create_event(
        EventInput(
            title="Morning",
            start_datetime=MIDNIGHT + timedelta(hours=9),
            end_datetime=MIDNIGHT + timedelta(hours=12),
        )
    )
    after = reminders.create_reminder(
        ReminderInput(
            title="After",
            reminder_datetime=MIDNIGHT + timedelta(hours=15),
        )
    )
    inside = reminders.create_reminder(
        ReminderInput(
            title="Inside",
            reminder_datetime=MIDNIGHT + timedelta(hours=11),
        )
    )
    assert schedule.get_day_schedule(DAY) == [early, inside, late, after]


def test_same_timestamp_order_is_type_then_id(services: tuple) -> None:
    events, reminders, schedule = services
    instant = MIDNIGHT + timedelta(hours=11)
    first = reminders.create_reminder(
        ReminderInput(title="First", reminder_datetime=instant)
    )
    second = reminders.create_reminder(
        ReminderInput(title="Second", reminder_datetime=instant)
    )
    event = events.create_event(
        EventInput(
            title="Event",
            start_datetime=instant,
            end_datetime=instant + timedelta(hours=1),
        )
    )
    other = events.create_event(
        EventInput(
            title="Other",
            start_datetime=instant,
            end_datetime=instant + timedelta(hours=2),
        )
    )
    for _ in range(2):
        assert schedule.get_day_schedule(DAY) == [event, other, first, second]


@pytest.mark.parametrize(
    ("offset", "included"),
    [
        (timedelta(minutes=-1), False),
        (timedelta(0), True),
        (timedelta(days=1, microseconds=-1), True),
        (timedelta(days=1), False),
    ],
)
def test_reminder_day_boundaries(
    services: tuple, offset: timedelta, included: bool
) -> None:
    _, reminders, schedule = services
    saved = reminders.create_reminder(
        ReminderInput(
            title="Boundary",
            reminder_datetime=MIDNIGHT + offset,
        )
    )
    assert schedule.get_day_schedule(DAY) == ([saved] if included else [])


@pytest.mark.parametrize(
    ("start_hours", "end_hours", "included"),
    [
        (-1, 1, True),
        (23, 25, True),
        (-24, 48, True),
        (-1, 0, False),
        (24, 25, False),
    ],
)
def test_event_day_overlap(
    services: tuple, start_hours: int, end_hours: int, included: bool
) -> None:
    events, _, schedule = services
    saved = events.create_event(
        EventInput(
            title="Overlap",
            start_datetime=MIDNIGHT + timedelta(hours=start_hours),
            end_datetime=MIDNIGHT + timedelta(hours=end_hours),
        )
    )
    assert schedule.get_day_schedule(DAY) == ([saved] if included else [])


def test_empty_day_and_week(services: tuple) -> None:
    schedule = services[2]
    assert schedule.get_day_schedule(DAY) == []
    assert schedule.get_week_schedule(DAY) == {
        DAY + timedelta(days=offset): [] for offset in range(7)
    }


def test_week_boundaries_and_overnight_event(services: tuple) -> None:
    events, reminders, schedule = services
    saved = {}
    for offset in (-1, 0, 6, 7):
        saved[offset] = reminders.create_reminder(
            ReminderInput(
                title=str(offset),
                reminder_datetime=MIDNIGHT + timedelta(days=offset),
            )
        )
    overnight = events.create_event(
        EventInput(
            title="Overnight",
            start_datetime=MIDNIGHT + timedelta(hours=23),
            end_datetime=MIDNIGHT + timedelta(days=1, hours=1),
        )
    )
    previous = events.create_event(
        EventInput(
            title="Previous Sunday",
            start_datetime=MIDNIGHT - timedelta(hours=2),
            end_datetime=MIDNIGHT,
        )
    )
    following = events.create_event(
        EventInput(
            title="Next Monday",
            start_datetime=MIDNIGHT + timedelta(days=7),
            end_datetime=MIDNIGHT + timedelta(days=7, hours=1),
        )
    )
    week = schedule.get_week_schedule(DAY + timedelta(days=3))
    assert list(week) == [DAY + timedelta(days=i) for i in range(7)]
    assert week[DAY] == [saved[0], overnight]
    assert week[DAY + timedelta(days=1)] == [overnight]
    assert week[DAY + timedelta(days=6)] == [saved[6]]
    combined = [item for items in week.values() for item in items]
    assert all(
        item not in combined for item in (saved[-1], saved[7], previous, following)
    )


def test_arbitrary_range_and_no_mutation(services: tuple) -> None:
    events, reminders, schedule = services
    event = events.create_event(
        EventInput(
            title="Wide",
            start_datetime=MIDNIGHT,
            end_datetime=MIDNIGHT + timedelta(hours=12),
        )
    )
    reminder = reminders.create_reminder(
        ReminderInput(
            title="Inside",
            reminder_datetime=MIDNIGHT + timedelta(hours=10),
        )
    )
    before = schedule.list_items()
    assert schedule.get_schedule_between(
        MIDNIGHT + timedelta(hours=10), MIDNIGHT + timedelta(hours=11)
    ) == [event, reminder]
    schedule.get_week_schedule(DAY)
    assert schedule.list_items() == before


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (MIDNIGHT, MIDNIGHT),
        (MIDNIGHT + timedelta(hours=1), MIDNIGHT),
        (MIDNIGHT.replace(tzinfo=UTC), MIDNIGHT + timedelta(hours=1)),
    ],
)
def test_invalid_ranges(services: tuple, start: datetime, end: datetime) -> None:
    with pytest.raises(InputValidationError):
        services[2].get_schedule_between(start, end)


@pytest.mark.parametrize("offset", range(7))
def test_week_starts_monday(offset: int) -> None:
    selected = DAY + timedelta(days=offset)
    assert get_week_start(selected) == DAY
    assert get_week_bounds(selected) == (MIDNIGHT, MIDNIGHT + timedelta(days=7))


def test_date_bounds_across_year_and_leap_day() -> None:
    assert get_day_bounds(date(2024, 2, 29)) == (
        datetime(2024, 2, 29),
        datetime(2024, 3, 1),
    )
    assert get_week_bounds(date(2027, 1, 1)) == (
        datetime(2026, 12, 28),
        datetime(2027, 1, 4),
    )
