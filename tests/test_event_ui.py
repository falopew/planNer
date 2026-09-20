"""Drive real Streamlit forms against a temporary persisted database."""

from datetime import time
from pathlib import Path

from pytest import MonkeyPatch
from streamlit.testing.v1 import AppTest

from src.database import db
from src.database.repositories import EventRepository
from src.services.event_service import EventService, EventStorageError

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def click(app: AppTest, label: str) -> AppTest:
    next(button for button in app.button if button.label == label).click()
    return app.run()


def test_create_edit_cancel_delete_and_restart(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    path = tmp_path / "planlayer.db"
    initialize = db.initialize_database
    monkeypatch.setattr(db, "initialize_database", lambda: initialize(path))
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any("No events yet" in message.value for message in app.info)
    app.text_input[0].set_value("Football Training")
    app.text_input[1].set_value("Football Pitch")
    app.text_area[0].set_value("Practice")
    app.time_input[0].set_value(time(19))
    app.time_input[1].set_value(time(21))
    app.selectbox[0].set_value("Sport")
    click(app, "Create event")
    assert not app.exception
    assert any(item.value == "Football Training" for item in app.subheader)
    app.run()
    engine = initialize(path)
    try:
        assert len(EventRepository(engine).list_events()) == 1
    finally:
        engine.dispose()

    # A fresh Streamlit session has no shared UI state but sees the saved event.
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any(item.value == "Football Training" for item in app.subheader)
    click(app, "Edit")
    assert app.text_input[0].value == "Football Training"
    app.text_input[0].set_value("Updated Training")
    click(app, "Save changes")
    assert not app.exception
    assert any(item.value == "Updated Training" for item in app.subheader)
    click(app, "Edit")
    app.text_input[0].set_value("Unsaved edit")
    click(app, "Cancel editing")
    assert any(item.value == "Updated Training" for item in app.subheader)
    click(app, "Delete")
    assert any("cannot be undone" in item.value for item in app.warning)
    click(app, "Cancel deletion")
    assert any(item.value == "Updated Training" for item in app.subheader)
    click(app, "Delete")
    click(app, "Confirm deletion")
    assert not app.exception
    assert any("No events yet" in item.value for item in app.info)
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any("No events yet" in item.value for item in app.info)


def test_missing_date_is_a_safe_validation_error(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    initialize = db.initialize_database
    monkeypatch.setattr(db, "initialize_database", lambda: initialize(tmp_path / "db"))
    app = AppTest.from_file(str(APP_PATH)).run()
    app.text_input[0].set_value("Training")
    app.date_input[0].set_value(None)
    click(app, "Create event")
    assert not app.exception
    assert app.error[0].value == "Start date and time are required."
    app = AppTest.from_file(str(APP_PATH)).run()
    assert any("No events yet" in item.value for item in app.info)


def test_validation_message_and_no_insert(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    initialize = db.initialize_database
    path = tmp_path / "planlayer.db"
    monkeypatch.setattr(db, "initialize_database", lambda: initialize(path))
    app = AppTest.from_file(str(APP_PATH)).run()
    click(app, "Create event")
    assert not app.exception
    assert app.error[0].value == "Title must not be empty."
    app.text_input[0].set_value("Training")
    app.time_input[0].set_value(time(12))
    app.time_input[1].set_value(time(10))
    click(app, "Create event")
    assert app.error[0].value == "End time must be later than start time."
    assert any("No events yet" in item.value for item in app.info)


def test_storage_error_is_displayed_safely(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    initialize = db.initialize_database
    monkeypatch.setattr(db, "initialize_database", lambda: initialize(tmp_path / "db"))

    def fail(self: EventService) -> list:
        raise EventStorageError("Could not access saved events.")

    monkeypatch.setattr(EventService, "list_events", fail)
    app = AppTest.from_file(str(APP_PATH)).run()
    assert not app.exception
    assert app.error[0].value == "Could not access saved events."
