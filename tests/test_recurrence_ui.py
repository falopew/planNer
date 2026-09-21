"""Shared repeat editors, whole-series changes and virtual calendar display."""

from datetime import date, time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.database import db
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.ui import calendar

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    initialize = db.initialize_database
    monkeypatch.setattr(
        db, "initialize_database", lambda: initialize(tmp_path / "test.db")
    )
    monkeypatch.setattr(calendar, "local_today", lambda: date(2026, 9, 21))
    application = AppTest.from_file(str(APP_PATH)).run()
    return application.radio(key="page").set_value("Events / Add Item").run()


def widget(app: AppTest, kind: str, label: str) -> object:
    return next(item for item in getattr(app, kind) if item.label == label)


def click(app: AppTest, label: str) -> AppTest:
    widget(app, "button", label).click()
    return app.run()


def choose(app: AppTest, label: str, value: object) -> AppTest:
    widget(app, "selectbox", label).set_value(value)
    return app.run()


def saved(kind: str) -> list:
    engine = db.initialize_database()
    try:
        repo = (
            EventRepository(engine) if kind == "event" else ReminderRepository(engine)
        )
        return getattr(repo, f"list_{kind}s")()
    finally:
        engine.dispose()


def fill(app: AppTest, kind: str) -> None:
    if kind == "reminder":
        app.radio(key="item_type").set_value("Reminder").run()
    app.text_input[0].set_value("Repeat me")
    widget(app, "date_input", "Date").set_value(date(2026, 9, 21))
    app.time_input[0].set_value(time(9))
    app.run()


@pytest.mark.parametrize(
    ("kind", "pattern", "future"),
    [
        ("event", "Daily", date(2026, 9, 22)),
        ("reminder", "Weekly", date(2026, 9, 28)),
    ],
)
def test_create_edit_remove_and_delete_whole_series(
    app: AppTest, kind: str, pattern: str, future: date
) -> None:
    fill(app, kind)
    choose(app, "Repeat", pattern)
    assert app.text_input[0].value == "Repeat me"  # repeat reruns keep the draft
    assert saved(kind) == []
    click(app, f"Create {kind}")
    assert not app.exception and not app.error
    original = saved(kind)[0]
    assert original.recurrence_rule == f"FREQ={pattern.upper()};INTERVAL=1"
    app.radio(key="page").set_value("Today").run()
    title = "Repeat me" if kind == "event" else "🔔 Repeat me"
    assert [item.value for item in app.subheader].count(title) == 1
    app.radio(key="page").set_value("Calendar").run()
    app.date_input(key="day_date").set_value(future).run()
    assert [item.value for item in app.subheader].count(title) == 1
    app.radio(key="calendar_view").set_value("Week").run()
    app.date_input(key="week_date").set_value(future).run()
    assert title in [item.value for item in app.subheader]
    app.radio(key="page").set_value("Events / Add Item").run()
    click(app, "Edit" if kind == "event" else "Edit reminder")
    assert widget(app, "selectbox", "Repeat").value == pattern
    assert any("entire series" in item.value for item in app.caption)
    choose(app, "Repeat", "Does not repeat")
    click(app, "Save changes" if kind == "event" else "Save reminder changes")
    assert saved(kind)[0].recurrence_rule is None
    assert saved(kind)[0].id == original.id
    app.radio(key="page").set_value("Calendar").run()
    app.radio(key="calendar_view").set_value("Day").run()
    app.date_input(key="day_date").set_value(future).run()
    assert title not in [item.value for item in app.subheader]
    app.radio(key="page").set_value("Events / Add Item").run()
    click(app, "Edit" if kind == "event" else "Edit reminder")
    choose(app, "Repeat", pattern)
    click(app, "Save changes" if kind == "event" else "Save reminder changes")
    click(app, "Delete" if kind == "event" else "Delete reminder")
    assert any("recurring series" in item.value for item in app.warning)
    click(app, "Confirm deletion" if kind == "event" else "Confirm reminder deletion")
    assert saved(kind) == []
    app.radio(key="page").set_value("Calendar").run()
    app.radio(key="calendar_view").set_value("Day").run()
    app.date_input(key="day_date").set_value(future).run()
    assert title not in [item.value for item in app.subheader]
    assert not app.exception


@pytest.mark.parametrize("kind", ["event", "reminder"])
def test_custom_weekdays_validation_end_date_and_edit(app: AppTest, kind: str) -> None:
    fill(app, kind)
    choose(app, "Repeat", "Custom weekly")
    click(app, f"Create {kind}")
    assert any("weekday" in item.value for item in app.error)
    assert not saved(kind)
    widget(app, "multiselect", "Repeat on").set_value(
        ["Monday", "Wednesday", "Friday"]
    ).run()
    choose(app, "Ends", "On date")
    widget(app, "date_input", "Recurrence end date").set_value(date(2026, 9, 20)).run()
    click(app, f"Create {kind}")
    assert any("precede" in item.value for item in app.error)
    widget(app, "date_input", "Recurrence end date").set_value(None).run()
    click(app, f"Create {kind}")
    assert any("Choose a recurrence end date" in item.value for item in app.error)
    widget(app, "date_input", "Recurrence end date").set_value(date(2026, 9, 25)).run()
    click(app, f"Create {kind}")
    assert not app.exception and not app.error
    assert (
        saved(kind)[0].recurrence_rule
        == "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR;UNTIL=20260925T235959"
    )
    click(app, "Edit" if kind == "event" else "Edit reminder")
    assert widget(app, "multiselect", "Repeat on").value == [
        "Monday",
        "Wednesday",
        "Friday",
    ]
    assert widget(app, "date_input", "Recurrence end date").value == date(2026, 9, 25)
    widget(app, "multiselect", "Repeat on").set_value(["Tuesday"]).run()
    click(app, "Save changes" if kind == "event" else "Save reminder changes")
    assert "BYDAY=TU;" in saved(kind)[0].recurrence_rule


@pytest.mark.parametrize(
    ("unit", "freq"), [("days", "DAILY"), ("weeks", "WEEKLY"), ("months", "MONTHLY")]
)
def test_custom_interval_controls(app: AppTest, unit: str, freq: str) -> None:
    fill(app, "event")
    choose(app, "Repeat", "Custom interval")
    widget(app, "number_input", "Every").set_value(3).run()
    choose(app, "Interval unit", unit)
    click(app, "Create event")
    assert not app.exception and not app.error
    assert saved("event")[0].recurrence_rule == f"FREQ={freq};INTERVAL=3"
    click(app, "Edit")
    assert widget(app, "selectbox", "Repeat").value == "Custom interval"
    assert widget(app, "number_input", "Every").value == 3
    assert widget(app, "selectbox", "Interval unit").value == unit


@pytest.mark.parametrize(
    ("pattern", "rule"),
    [
        ("Weekdays", "FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR"),
        ("Monthly", "FREQ=MONTHLY;INTERVAL=1"),
    ],
)
def test_other_presets_and_cancel_preserves_series(
    app: AppTest, pattern: str, rule: str
) -> None:
    fill(app, "reminder")
    choose(app, "Repeat", pattern)
    click(app, "Create reminder")
    original = saved("reminder")
    assert original[0].recurrence_rule == rule
    click(app, "Edit reminder")
    assert widget(app, "selectbox", "Repeat").value == pattern
    choose(app, "Repeat", "Daily")
    assert saved("reminder") == original
    click(app, "Cancel reminder editing")
    assert saved("reminder") == original
    assert not app.exception
