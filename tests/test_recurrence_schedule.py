"""Virtual occurrences preserve type, source identity, duration and stored rows."""

from collections.abc import Iterator
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy import event as sqlalchemy_event

from src.database.db import initialize_database
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import Event, EventInput
from src.models.reminder import Reminder, ReminderInput
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.services.schedule_service import ScheduleService, occurrence_identity

BASE = datetime(2026, 9, 21, 10)


@pytest.fixture
def context(
    tmp_path: Path,
) -> Iterator[tuple[Engine, EventService, ReminderService, ScheduleService]]:
    engine = initialize_database(tmp_path / "recurrence.db")
    events = EventService(EventRepository(engine))
    reminders = ReminderService(ReminderRepository(engine))
    try:
        yield engine, events, reminders, ScheduleService(events, reminders)
    finally:
        engine.dispose()


def test_mixed_order_no_duplicates_duration_and_no_materialization(
    context: tuple,
) -> None:
    _, events, reminders, schedule = context
    recurring = events.create_event(
        EventInput(
            title="Lecture",
            start_datetime=BASE,
            end_datetime=BASE + timedelta(hours=2),
            recurrence_rule="FREQ=DAILY",
        )
    )
    once = events.create_event(
        EventInput(
            title="Meeting",
            start_datetime=BASE,
            end_datetime=BASE + timedelta(hours=1),
        )
    )
    bell = reminders.create_reminder(
        ReminderInput(
            title="Daily bell",
            reminder_datetime=BASE,
            recurrence_rule="FREQ=DAILY",
        )
    )
    inside = reminders.create_reminder(
        ReminderInput(
            title="Inside",
            reminder_datetime=BASE + timedelta(hours=1),
        )
    )
    before = schedule.list_items()
    day = schedule.get_day_schedule(BASE.date())
    assert day == [recurring, once, bell, inside]
    assert len({occurrence_identity(item) for item in day}) == 4
    tomorrow = schedule.get_day_schedule(date(2026, 9, 22))
    assert [item.title for item in tomorrow] == ["Lecture", "Daily bell"]
    assert isinstance(tomorrow[0], Event) and isinstance(tomorrow[1], Reminder)
    assert tomorrow[0].id == recurring.id and tomorrow[1].id == bell.id
    assert tomorrow[0].end_datetime - tomorrow[0].start_datetime == timedelta(hours=2)
    assert (
        not {"start_datetime", "end_datetime", "duration"} & asdict(tomorrow[1]).keys()
    )
    assert occurrence_identity(tomorrow[0]) == (
        "event",
        recurring.id,
        BASE + timedelta(days=1),
    )
    week = schedule.get_week_schedule(date(2026, 9, 23))
    assert list(week) == [date(2026, 9, 21) + timedelta(days=i) for i in range(7)]
    assert [len(items) for items in week.values()] == [4, 2, 2, 2, 2, 2, 2]
    assert schedule.list_items() == before
    assert len(events.list_events()) == 2
    assert len(reminders.list_reminders()) == 2


@pytest.mark.parametrize("duration", [timedelta(hours=2), timedelta(days=2, hours=2)])
def test_overlap_expands_backwards_even_for_long_events(
    context: tuple, duration: timedelta
) -> None:
    _, events, _, schedule = context
    start = datetime(2026, 9, 20, 23)
    series = events.create_event(
        EventInput(
            title="Night shift",
            start_datetime=start,
            end_datetime=start + duration,
            recurrence_rule="FREQ=DAILY",
        )
    )
    lower = datetime(2026, 9, 23)
    upper = datetime(2026, 9, 24)
    expected = [
        replace(
            series,
            start_datetime=start + timedelta(days=i),
            end_datetime=start + timedelta(days=i) + duration,
        )
        for i in range(4)
        if start + timedelta(days=i) < upper
        and start + timedelta(days=i) + duration > lower
    ]
    assert schedule.get_schedule_between(lower, upper) == expected
    assert schedule.get_week_schedule(lower.date())[lower.date()] == expected


def test_exact_overlap_and_reminder_boundaries(context: tuple) -> None:
    _, events, reminders, schedule = context
    events.create_event(
        EventInput(
            title="Night",
            start_datetime=BASE.replace(hour=23),
            end_datetime=BASE.replace(hour=23) + timedelta(hours=1),
            recurrence_rule="FREQ=DAILY",
        )
    )
    reminders.create_reminder(
        ReminderInput(
            title="Midnight",
            reminder_datetime=BASE.replace(hour=0),
            recurrence_rule="FREQ=DAILY",
        )
    )
    lower = datetime(2026, 9, 22)
    items = schedule.get_schedule_between(lower, lower + timedelta(days=1))
    assert [item.title for item in items] == ["Midnight", "Night"]
    assert items[0].reminder_datetime == lower
    assert items[1].start_datetime == lower.replace(hour=23)


@pytest.mark.parametrize("kind", ["event", "reminder"])
def test_edit_remove_and_delete_series(context: tuple, kind: str) -> None:
    _, events, reminders, schedule = context
    service = events if kind == "event" else reminders
    data = (
        EventInput(
            title="Series",
            start_datetime=BASE,
            end_datetime=BASE + timedelta(hours=2),
            recurrence_rule="FREQ=DAILY",
        )
        if kind == "event"
        else ReminderInput(
            title="Series", reminder_datetime=BASE, recurrence_rule="FREQ=DAILY"
        )
    )
    saved = getattr(service, f"create_{kind}")(data)
    assert len(schedule.get_day_schedule(date(2026, 9, 22))) == 1
    getattr(service, f"update_{kind}")(
        saved.id, replace(data, recurrence_rule="FREQ=WEEKLY;BYDAY=FR")
    )
    assert schedule.get_day_schedule(date(2026, 9, 21)) == []
    assert schedule.get_day_schedule(date(2026, 9, 22)) == []
    assert len(schedule.get_day_schedule(date(2026, 9, 25))) == 1
    getattr(service, f"update_{kind}")(saved.id, replace(data, recurrence_rule=None))
    assert len(schedule.get_day_schedule(date(2026, 9, 21))) == 1
    assert schedule.get_day_schedule(date(2026, 9, 25)) == []
    getattr(service, f"update_{kind}")(saved.id, data)
    assert getattr(service, f"delete_{kind}")(saved.id)
    assert all(not items for items in schedule.get_week_schedule(BASE.date()).values())


def test_week_uses_constant_number_of_queries(context: tuple) -> None:
    engine, events, reminders, schedule = context
    for i in range(10):
        events.create_event(
            EventInput(
                title=f"Event {i}",
                start_datetime=BASE,
                end_datetime=BASE + timedelta(hours=1),
                recurrence_rule="FREQ=DAILY",
            )
        )
        reminders.create_reminder(
            ReminderInput(
                title=f"Reminder {i}",
                reminder_datetime=BASE,
                recurrence_rule="FREQ=DAILY",
            )
        )
    statements = []

    def record(
        connection: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    sqlalchemy_event.listen(engine, "before_cursor_execute", record)
    try:
        assert sum(map(len, schedule.get_week_schedule(BASE.date()).values())) == 140
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", record)
    assert len(statements) == 4
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)


def test_until_limits_starts_not_overnight_ends(context: tuple) -> None:
    _, events, _, schedule = context
    base = datetime(2026, 9, 21, 23)
    events.create_event(
        EventInput(
            title="Last night",
            start_datetime=base,
            end_datetime=base + timedelta(hours=2),
            recurrence_rule="FREQ=DAILY;UNTIL=20260921T235959",
        )
    )
    assert len(schedule.get_day_schedule(date(2026, 9, 22))) == 1
    assert (
        schedule.get_schedule_between(datetime(2026, 9, 22, 1), datetime(2026, 9, 23))
        == []
    )


@pytest.mark.parametrize("kind", ["event", "reminder"])
def test_moving_anchor_changes_implicit_weekday(context: tuple, kind: str) -> None:
    _, events, reminders, schedule = context
    friday = datetime(2026, 9, 25, 19)
    if kind == "event":
        data = EventInput(
            title="Weekly",
            start_datetime=friday,
            end_datetime=friday + timedelta(hours=2),
            recurrence_rule="FREQ=WEEKLY",
        )
        saved = events.create_event(data)
        events.update_event(
            saved.id,
            replace(
                data,
                start_datetime=friday + timedelta(days=1),
                end_datetime=friday + timedelta(days=1, hours=2),
            ),
        )
    else:
        data = ReminderInput(
            title="Weekly", reminder_datetime=friday, recurrence_rule="FREQ=WEEKLY"
        )
        saved = reminders.create_reminder(data)
        reminders.update_reminder(
            saved.id, replace(data, reminder_datetime=friday + timedelta(days=1))
        )
    assert schedule.get_day_schedule(date(2026, 10, 2)) == []
    assert len(schedule.get_day_schedule(date(2026, 10, 3))) == 1
