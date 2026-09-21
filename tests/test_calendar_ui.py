"""Read-only calendar navigation and presentation through Streamlit."""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.database import db
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import EventInput
from src.models.reminder import ReminderInput
from src.services.event_service import EventService, EventStorageError
from src.services.reminder_service import ReminderService, ReminderStorageError
from src.ui import calendar

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
TODAY = date(2026, 9, 21)


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "calendar.db"
    initialize = db.initialize_database
    monkeypatch.setattr(db, "initialize_database", lambda: initialize(path))
    monkeypatch.setattr(calendar, "local_today", lambda: TODAY)
    return path


def click(app: AppTest, label: str) -> AppTest:
    next(button for button in app.button if button.label == label).click()
    return app.run()


def seed() -> tuple[list, list]:
    engine = db.initialize_database()
    try:
        events = EventService(EventRepository(engine))
        reminders = ReminderService(ReminderRepository(engine))
        events.create_event(
            EventInput(
                title="Lecture",
                start_datetime=datetime(2026, 9, 21, 10),
                end_datetime=datetime(2026, 9, 21, 12),
                category="University",
                location="Campus",
                description="Bring notes",
            )
        )
        reminders.create_reminder(
            ReminderInput(
                title="Medication",
                reminder_datetime=datetime(2026, 9, 21, 11),
                category="Health",
            )
        )
        reminders.create_reminder(
            ReminderInput(
                title="Tomorrow item",
                reminder_datetime=datetime(2026, 9, 22, 9),
            )
        )
        return events.list_events(), reminders.list_reminders()
    finally:
        engine.dispose()


def test_default_today_and_distinct_types(database: Path) -> None:
    seed()
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert app.radio(key="page").value == "Today"
    assert [item.value for item in app.subheader][-2:] == ["Lecture", "🔔 Medication"]
    captions = [item.value for item in app.caption]
    assert "Fixed Event · 10:00 – 12:00" in captions
    assert "Reminder · 11:00 · Health · No occupied time" in captions
    assert not any("Tomorrow item" in item.value for item in app.subheader)
    assert "Location: Campus" in [item.value for item in app.text]
    assert "Bring notes" in [item.value for item in app.text]
    assert not any(
        "Edit" in button.label or "Delete" in button.label for button in app.button
    )


def test_navigation_dates_week_and_no_writes(database: Path) -> None:
    before = seed()
    app = AppTest.from_file(str(APP_PATH)).run()
    click(app, "Tomorrow")
    assert app.radio(key="page").value == "Calendar"
    assert app.date_input(key="day_date").value == TODAY + timedelta(days=1)
    assert "🔔 Tomorrow item" in [item.value for item in app.subheader]
    click(app, "Previous Day")
    assert "Lecture" in [item.value for item in app.subheader]
    click(app, "Next Day")
    click(app, "Today")
    assert app.date_input(key="day_date").value == TODAY
    app.date_input(key="day_date").set_value(date(2026, 9, 30)).run()
    assert any("No plans or reminders" in item.value for item in app.info)
    app.radio(key="calendar_view").set_value("Week").run()
    assert "21 Sep 2026" in app.header[0].value
    assert "27 Sep 2026" in app.header[0].value
    assert len([item for item in app.info if item.value == "No items"]) == 5
    assert "Lecture" in [item.value for item in app.subheader]
    assert "🔔 Medication" in [item.value for item in app.subheader]
    click(app, "Next Week")
    assert app.date_input(key="week_date").value == date(2026, 9, 28)
    assert len(app.info) == 7
    click(app, "Previous Week")
    click(app, "Previous Week")
    click(app, "Current Week")
    assert app.date_input(key="week_date").value == TODAY
    app.date_input(key="week_date").set_value(date(2026, 9, 27)).run()
    assert "21 Sep 2026" in app.header[0].value
    app.radio(key="page").set_value("Today").run()
    assert "Lecture" in [item.value for item in app.subheader]
    assert not app.exception
    engine = db.initialize_database()
    try:
        assert (
            EventRepository(engine).list_events(),
            ReminderRepository(engine).list_reminders(),
        ) == before
    finally:
        engine.dispose()


def test_overnight_event_keeps_dates_in_both_day_agendas(database: Path) -> None:
    engine = db.initialize_database()
    try:
        EventService(EventRepository(engine)).create_event(
            EventInput(
                title="Night shift",
                start_datetime=datetime(2026, 9, 21, 23),
                end_datetime=datetime(2026, 9, 22, 1),
            )
        )
    finally:
        engine.dispose()
    app = AppTest.from_file(str(APP_PATH)).run()
    expected = "Fixed Event · 21 Sep 2026 23:00 – 22 Sep 2026 01:00"
    assert expected in [item.value for item in app.caption]
    click(app, "Tomorrow")
    assert expected in [item.value for item in app.caption]
    assert not app.exception


def test_empty_and_cleared_selection(database: Path) -> None:
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any("No plans or reminders" in item.value for item in app.info)
    app.radio(key="page").set_value("Calendar").run()
    app.date_input(key="day_date").set_value(None).run()
    assert not app.exception
    assert any("Choose a date" in item.value for item in app.info)
    click(app, "Today")
    assert app.date_input(key="day_date").value == TODAY
    app.radio(key="calendar_view").set_value("Week").run()
    assert len(app.info) == 7
    app.date_input(key="week_date").set_value(None).run()
    assert not app.exception
    assert any("Choose a date" in item.value for item in app.info)


@pytest.mark.parametrize("kind", ["events", "reminders"])
def test_calendar_safe_storage_errors(
    database: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    def fail(*args: object) -> list:
        if kind == "events":
            raise EventStorageError("Could not access saved events.")
        raise ReminderStorageError("Could not access saved reminders.")

    if kind == "events":
        monkeypatch.setattr(EventService, "get_events_between", fail)
    else:
        monkeypatch.setattr(ReminderService, "get_reminders_between", fail)
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert app.error
    app.radio(key="page").set_value("Calendar").run()
    app.radio(key="calendar_view").set_value("Week").run()
    assert not app.exception
    assert app.error
