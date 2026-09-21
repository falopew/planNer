"""Reminder form workflows and mixed schedule display through Streamlit."""

from datetime import date, time
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from src.database import db
from src.database.reminder_repository import ReminderRepository
from src.services.reminder_service import ReminderService, ReminderStorageError

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def click(app: AppTest, label: str) -> AppTest:
    next(button for button in app.button if button.label == label).click()
    return app.run()


def reminder_app(tmp_path: Path, monkeypatch: MonkeyPatch) -> AppTest:
    initialize = db.initialize_database
    monkeypatch.setattr(
        db, "initialize_database", lambda: initialize(tmp_path / "planlayer.db")
    )
    app = AppTest.from_file(str(APP_PATH)).run()
    app.radio[0].set_value("Reminder").run()
    return app


def test_reminder_crud_and_restart(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = reminder_app(tmp_path, monkeypatch)
    assert any(item.value == "No reminders yet." for item in app.info)
    assert [widget.label for widget in app.time_input] == ["Time"]
    app.text_input[0].set_value("Take medication")
    app.text_area[0].set_value("With water")
    app.date_input[0].set_value(date(2026, 9, 22))
    app.time_input[0].set_value(time(9))
    app.selectbox[0].set_value("Health")
    click(app, "Create reminder")
    assert not app.exception
    assert any(item.value == "🔔 Take medication" for item in app.subheader)
    app.run()
    engine = db.initialize_database()
    try:
        assert len(ReminderRepository(engine).list_reminders()) == 1
    finally:
        engine.dispose()
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any(item.value == "🔔 Take medication" for item in app.subheader)
    click(app, "Edit reminder")
    assert app.radio[0].value == "Reminder"
    assert app.text_input[0].value == "Take medication"
    app.text_input[0].set_value("Bring shoes")
    app.time_input[0].set_value(time(18, 30))
    click(app, "Save reminder changes")
    assert any(item.value == "🔔 Bring shoes" for item in app.subheader)
    click(app, "Edit reminder")
    app.text_input[0].set_value("Unsaved")
    click(app, "Cancel reminder editing")
    assert any(item.value == "🔔 Bring shoes" for item in app.subheader)
    click(app, "Delete reminder")
    click(app, "Cancel reminder deletion")
    assert any(item.value == "🔔 Bring shoes" for item in app.subheader)
    click(app, "Delete reminder")
    click(app, "Confirm reminder deletion")
    assert not app.exception
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any(item.value == "No reminders yet." for item in app.info)


@pytest.mark.parametrize("title", ["", "   "])
def test_title_validation(tmp_path: Path, monkeypatch: MonkeyPatch, title: str) -> None:
    app = reminder_app(tmp_path, monkeypatch)
    app.text_input[0].set_value(title)
    click(app, "Create reminder")
    assert not app.exception
    assert app.error[0].value == "Title must not be empty."
    assert any(item.value == "No reminders yet." for item in app.info)


@pytest.mark.parametrize("field", ["date_input", "time_input"])
def test_cleared_datetime(tmp_path: Path, monkeypatch: MonkeyPatch, field: str) -> None:
    app = reminder_app(tmp_path, monkeypatch)
    app.text_input[0].set_value("Bring shoes")
    getattr(app, field)[0].set_value(None)
    click(app, "Create reminder")
    assert not app.exception
    assert app.error[0].value == "Reminder date and time are required."


def test_reminder_inside_event_and_type_switching(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = reminder_app(tmp_path, monkeypatch)
    app.radio[0].set_value("Fixed Event").run()
    app.text_input[0].set_value("Lecture")
    app.time_input[0].set_value(time(10))
    app.time_input[1].set_value(time(12))
    click(app, "Create event")
    app.radio[0].set_value("Reminder").run()
    for title in ("Take medication", "Submit form"):
        app.text_input[0].set_value(title)
        app.time_input[0].set_value(time(11))
        click(app, "Create reminder")
    titles = [item.value for item in app.subheader]
    assert titles[-3:] == ["Lecture", "🔔 Take medication", "🔔 Submit form"]
    assert not app.error
    assert not app.warning
    click(app, "Edit")
    assert app.radio[0].value == "Fixed Event"
    assert app.text_input[0].value == "Lecture"
    click(app, "Cancel editing")
    app = AppTest.from_file(str(APP_PATH)).run()
    assert [item.value for item in app.subheader][-3:] == titles[-3:]


def test_storage_error_safe(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = reminder_app(tmp_path, monkeypatch)

    def fail(self: ReminderService) -> list:
        raise ReminderStorageError("Could not access saved reminders.")

    monkeypatch.setattr(ReminderService, "list_reminders", fail)
    app.run()
    assert not app.exception
    assert app.error[0].value == "Could not access saved reminders."
