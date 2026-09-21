"""Reminder CRUD, range boundaries and separation from event occupancy."""

import subprocess
import sys
from collections.abc import Iterator
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import URL, create_engine, inspect
from sqlalchemy.exc import IntegrityError

from src.database.db import check_database_health, initialize_database
from src.database.models import EventRecord
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import Event, EventInput
from src.models.reminder import ReminderInput
from src.services.event_service import EventService
from src.services.reminder_service import (
    ReminderService,
    ReminderStorageError,
    ReminderValidationError,
)
from src.services.schedule_service import ScheduleService


def reminder_input(hour: int = 9, minute: int = 0) -> ReminderInput:
    return ReminderInput(
        title="Take medication",
        reminder_datetime=datetime(2026, 9, 22, hour, minute),
        category="Health",
    )


@pytest.fixture
def service(tmp_path: Path) -> Iterator[ReminderService]:
    engine = initialize_database(tmp_path / "planlayer.db")
    try:
        yield ReminderService(ReminderRepository(engine))
    finally:
        engine.dispose()


def test_creation_normalizes_all_fields(service: ReminderService) -> None:
    saved = service.create_reminder(
        replace(
            reminder_input(),
            title=" Take medication ",
            description=" With water ",
            category=" Health ",
        )
    )
    assert saved.title == "Take medication"
    assert saved.description == "With water"
    assert saved.category == "Health"
    assert saved.reminder_datetime == datetime(2026, 9, 22, 9)
    assert saved.id > 0
    assert saved.created_at == saved.updated_at
    assert saved.created_at.tzinfo is None
    assert service.get_reminder(saved.id) == saved
    assert not isinstance(saved, Event)
    assert not {"start_datetime", "end_datetime", "duration"} & asdict(saved).keys()


@pytest.mark.parametrize("title", ["", "   ", "\t\n", "x" * 201, None])
def test_invalid_title_rejected(service: ReminderService, title: str) -> None:
    with pytest.raises(ReminderValidationError, match="Title"):
        service.create_reminder(replace(reminder_input(), title=title))
    assert service.list_reminders() == []


@pytest.mark.parametrize(
    "moment", [None, "2026-09-22", datetime.fromisoformat("2026-09-22T09:00:00+08:00")]
)
def test_required_local_naive_datetime(
    service: ReminderService, moment: object
) -> None:
    with pytest.raises(ReminderValidationError):
        service.create_reminder(replace(reminder_input(), reminder_datetime=moment))
    assert service.list_reminders() == []


def test_default_category_and_title_boundary(service: ReminderService) -> None:
    saved = service.create_reminder(
        replace(reminder_input(), title="x" * 200, category="  ")
    )
    assert saved.category == "Other"
    assert saved.description == ""


def test_update_preserves_identity(service: ReminderService) -> None:
    old = service.create_reminder(reminder_input())
    changed = replace(
        reminder_input(11),
        title="Bring documents",
        category="University",
        description="Passport",
    )
    saved = service.update_reminder(old.id, changed)
    assert saved is not None
    assert saved.id == old.id
    assert saved.created_at == old.created_at
    assert saved.updated_at > old.updated_at
    for key, value in asdict(changed).items():
        assert getattr(saved, key) == value
    assert service.get_reminder(old.id) == saved
    with pytest.raises(ReminderValidationError):
        service.update_reminder(old.id, replace(changed, title=" "))
    assert service.get_reminder(old.id) == saved


def test_delete_and_missing_ids(service: ReminderService) -> None:
    assert service.get_reminder(999) is None
    assert service.update_reminder(999, reminder_input()) is None
    assert service.delete_reminder(999) is False
    saved = service.create_reminder(reminder_input())
    assert service.delete_reminder(saved.id) is True
    assert service.get_reminder(saved.id) is None
    assert service.delete_reminder(saved.id) is False


def test_order_and_identical_timestamps(service: ReminderService) -> None:
    for hour in (18, 9, 14, 9):
        service.create_reminder(reminder_input(hour))
    saved = service.list_reminders()
    assert [item.reminder_datetime.hour for item in saved] == [9, 9, 14, 18]
    assert saved[0].id < saved[1].id


def test_half_open_range_includes_start_excludes_end(service: ReminderService) -> None:
    values = [(9, 0), (10, 0), (10, 30), (13, 30), (14, 0), (14, 30)]
    for hour, minute in values:
        service.create_reminder(reminder_input(hour, minute))
    saved = service.get_reminders_between(
        datetime(2026, 9, 22, 10), datetime(2026, 9, 22, 14)
    )
    assert [
        (item.reminder_datetime.hour, item.reminder_datetime.minute) for item in saved
    ] == [(10, 0), (10, 30), (13, 30)]


@pytest.mark.parametrize("start,end", [(14, 10), (10, 10)])
def test_invalid_range(service: ReminderService, start: int, end: int) -> None:
    with pytest.raises(ReminderValidationError):
        service.get_reminders_between(
            datetime(2026, 9, 22, start), datetime(2026, 9, 22, end)
        )


def test_coexistence_and_display_do_not_change_events(tmp_path: Path) -> None:
    engine = initialize_database(tmp_path / "planlayer.db")
    events = EventService(EventRepository(engine))
    reminders = ReminderService(ReminderRepository(engine))
    try:
        lecture = events.create_event(
            EventInput(
                title="Lecture",
                start_datetime=datetime(2026, 9, 22, 10),
                end_datetime=datetime(2026, 9, 22, 12),
            )
        )
        first = reminders.create_reminder(reminder_input(11))
        second = reminders.create_reminder(
            replace(reminder_input(11), title="Submit form")
        )
        before = reminders.create_reminder(reminder_input(9))
        same_start = reminders.create_reminder(reminder_input(10))
        assert ScheduleService(events, reminders).list_items() == [
            before,
            lecture,
            same_start,
            first,
            second,
        ]
        assert events.get_events_between(
            datetime(2026, 9, 22, 10), datetime(2026, 9, 22, 12)
        ) == [lecture]
        reminders.update_reminder(first.id, reminder_input(10))
        reminders.delete_reminder(first.id)
        assert events.get_event(lecture.id) == lecture
        assert events.list_events() == [lecture]
        assert check_database_health(engine)
    finally:
        engine.dispose()


def test_upgrade_preserves_existing_event_rows(tmp_path: Path) -> None:
    path = tmp_path / "planlayer.db"
    engine = create_engine(URL.create("sqlite", database=str(path)))
    EventRecord.__table__.create(engine)
    event = EventService(EventRepository(engine)).create_event(
        EventInput(
            title="Existing lecture",
            start_datetime=datetime(2026, 9, 22, 10),
            end_datetime=datetime(2026, 9, 22, 12),
        )
    )
    engine.dispose()
    engine = initialize_database(path)
    try:
        assert inspect(engine).get_table_names() == ["events", "reminders"]
        assert EventRepository(engine).get_event(event.id) == event
        ReminderService(ReminderRepository(engine)).create_reminder(reminder_input())
    finally:
        engine.dispose()


def test_new_process_persistence(tmp_path: Path) -> None:
    path = tmp_path / "planlayer.db"
    engine = initialize_database(path)
    saved = ReminderService(ReminderRepository(engine)).create_reminder(
        reminder_input()
    )
    engine.dispose()
    script = """
import sys
from pathlib import Path
from src.database.db import initialize_database
from src.database.reminder_repository import ReminderRepository
engine = initialize_database(Path(sys.argv[1]))
try:
    reminder = ReminderRepository(engine).get_reminder(int(sys.argv[2]))
    assert reminder.title == 'Take medication'
finally:
    engine.dispose()
"""
    subprocess.run(
        [sys.executable, "-c", script, str(path), str(saved.id)],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def test_constraints_rollback_and_no_interval_columns(tmp_path: Path) -> None:
    engine = initialize_database(tmp_path / "db")
    repo = ReminderRepository(engine)
    try:
        with pytest.raises(IntegrityError):
            repo.create_reminder(replace(reminder_input(), reminder_datetime=None))
        assert repo.list_reminders() == []
        assert repo.create_reminder(reminder_input()).id > 0
        columns = {
            column["name"] for column in inspect(engine).get_columns("reminders")
        }
        assert columns == {
            "id",
            "title",
            "description",
            "reminder_datetime",
            "category",
            "created_at",
            "updated_at",
        }
    finally:
        engine.dispose()


def test_safe_storage_failure(tmp_path: Path) -> None:
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "missing" / "db"))
    )
    try:
        with pytest.raises(
            ReminderStorageError, match="Could not access saved reminders"
        ):
            ReminderService(ReminderRepository(engine)).list_reminders()
    finally:
        engine.dispose()
