"""Real recurrence/service integration and read-only calendar warning workflows."""

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event as sqlalchemy_event
from streamlit.testing.v1 import AppTest

from src.database import db
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import EventInput
from src.models.reminder import ReminderInput
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.services.schedule_service import ScheduleService
from src.ui import calendar

DAY = date(2026, 11, 4)
START = datetime(2026, 11, 4)
APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple]:
    initialize = db.initialize_database
    monkeypatch.setattr(
        db, "initialize_database", lambda: initialize(tmp_path / "test.db")
    )
    monkeypatch.setattr(calendar, "local_today", lambda: DAY)
    engine = db.initialize_database()
    events = EventService(EventRepository(engine))
    reminders = ReminderService(ReminderRepository(engine))
    try:
        yield engine, events, reminders, ScheduleService(events, reminders)
    finally:
        engine.dispose()


def seed(events: EventService, reminders: ReminderService) -> None:
    for title, start, end in [("Lecture", 10, 12), ("Meeting", 11, 13)]:
        events.create_event(
            EventInput(
                title=title,
                start_datetime=START + timedelta(hours=start),
                end_datetime=START + timedelta(hours=end),
                recurrence_rule="FREQ=DAILY",
            )
        )
    reminders.create_reminder(
        ReminderInput(
            title="Medication",
            reminder_datetime=START + timedelta(hours=11),
            recurrence_rule="FREQ=DAILY",
        )
    )


def test_recurring_conflicts_week_queries_and_no_writes(services: tuple) -> None:
    engine, events, reminders, schedule = services
    seed(events, reminders)
    before = schedule.list_items()
    tomorrow = schedule.get_day_agenda(DAY + timedelta(days=1))
    assert len(tomorrow.items) == 3 and len(tomorrow.conflicts) == 1
    assert tomorrow.conflicts[0].overlap_start == START + timedelta(days=1, hours=11)
    statements = []

    def record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    sqlalchemy_event.listen(engine, "before_cursor_execute", record)
    try:
        week = schedule.get_week_agenda(DAY)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", record)
    assert (
        len(week.conflicts) == 5
    )  # Wednesday through Sunday, no starts before anchor.
    assert len(statements) == 4
    assert all(s.lstrip().startswith("SELECT") for s in statements)
    assert schedule.list_items() == before


def test_long_pair_counted_once_per_week_and_clipped_per_day(services: tuple) -> None:
    _, events, _, schedule = services
    for title, start, end in [("Long A", -2, 28), ("Long B", -1, 27)]:
        events.create_event(
            EventInput(
                title=title,
                start_datetime=START + timedelta(hours=start),
                end_datetime=START + timedelta(hours=end),
            )
        )
    assert len(schedule.get_week_agenda(DAY).conflicts) == 1
    conflict = schedule.get_day_agenda(DAY).conflicts[0]
    assert conflict.overlap_start == START
    assert conflict.overlap_end == START + timedelta(days=1)


def test_ui_today_day_week_and_resolution(services: tuple) -> None:
    _, events, reminders, schedule = services
    seed(events, reminders)
    before = schedule.list_items()
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception
    assert any("1 event conflict" in item.value for item in app.warning)
    assert any(
        "Lecture ↔ Meeting" in item.value
        and "11:00" in item.value
        and "12:00" in item.value
        for item in app.text
    )
    assert "🔔 Medication" in [item.value for item in app.subheader]
    app.radio(key="page").set_value("Calendar").run()
    app.date_input(key="day_date").set_value(DAY + timedelta(days=1)).run()
    assert any("1 event conflict" in item.value for item in app.warning)
    app.radio(key="calendar_view").set_value("Week").run()
    assert any("5 event conflict" in item.value for item in app.warning)
    assert schedule.list_items() == before
    # Move the second series to be adjacent, not overlapping, through existing CRUD.
    app.radio(key="page").set_value("Events / Add Item").run()
    meeting = next(item for item in events.list_events() if item.title == "Meeting")
    app.button(key=f"edit_{meeting.id}").click().run()
    next(item for item in app.time_input if item.label == "Start time").set_value(
        (START + timedelta(hours=12)).time()
    )
    next(item for item in app.button if item.label == "Save changes").click().run()
    app.radio(key="page").set_value("Today").run()
    assert not app.exception and not app.warning
    assert any("No event conflicts" in item.value for item in app.caption)
    assert len(events.list_events()) == 2 and len(reminders.list_reminders()) == 1


def test_reminder_and_adjacent_events_do_not_warn(services: tuple) -> None:
    _, events, reminders, _ = services
    for start in (9, 10):
        events.create_event(
            EventInput(
                title=str(start),
                start_datetime=START + timedelta(hours=start),
                end_datetime=START + timedelta(hours=start + 1),
            )
        )
    reminders.create_reminder(
        ReminderInput(title="Bell", reminder_datetime=START.replace(hour=10))
    )
    app = AppTest.from_file(str(APP)).run()
    assert not app.exception and not app.warning
    app.radio(key="page").set_value("Calendar").run()
    app.radio(key="calendar_view").set_value("Week").run()
    assert not app.exception and not app.warning
