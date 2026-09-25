"""Real M3 schema upgrade, series persistence and service validation."""

import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from src.database.db import check_database_health, initialize_database
from src.database.reminder_repository import ReminderRepository
from src.database.repositories import EventRepository
from src.models.event import EventInput
from src.models.reminder import ReminderInput
from src.services.event_service import EventService
from src.services.reminder_service import ReminderService
from src.services.validation import InputValidationError


def test_upgrade_real_m3_schema_preserves_every_field(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    # Deliberately independent of current ORM metadata: no recurrence columns.
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE events (
                id INTEGER PRIMARY KEY, title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL, start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL, category VARCHAR NOT NULL,
                location VARCHAR NOT NULL, created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                CHECK(end_datetime > start_datetime)
            );
            CREATE INDEX ix_events_start_datetime ON events(start_datetime);
            CREATE TABLE reminders (
                id INTEGER PRIMARY KEY, title VARCHAR(200) NOT NULL,
                description TEXT NOT NULL, reminder_datetime DATETIME NOT NULL,
                category VARCHAR NOT NULL, created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            );
            INSERT INTO events VALUES
                (7, 'Lecture', 'Notes', '2026-09-21 10:00:00', '2026-09-21 12:00:00',
                 'University', 'Campus', '2026-09-20 08:00:00', '2026-09-20 09:00:00');
            INSERT INTO reminders VALUES
                (11, 'Medication', 'Water', '2026-09-21 11:00:00',
                 'Health', '2026-09-20 08:00:00', '2026-09-20 09:00:00');
        """)
        originals = {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in ("events", "reminders")
        }
    for _ in range(3):
        engine = initialize_database(path)
        try:
            assert check_database_health(engine)
            for table in ("events", "reminders"):
                columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
                assert columns["recurrence_rule"]["nullable"]
                with engine.connect() as connection:
                    rows = connection.execute(text(f"SELECT * FROM {table}")).fetchall()
                    assert [tuple(row[:-1]) for row in rows] == originals[table]
                    assert all(row[-1] is None for row in rows)
            assert EventRepository(engine).get_event(7).recurrence_rule is None
            assert ReminderRepository(engine).get_reminder(11).recurrence_rule is None
            assert (
                inspect(engine).get_indexes("events")[0]["name"]
                == "ix_events_start_datetime"
            )
        finally:
            engine.dispose()


@pytest.mark.parametrize("kind", ["event", "reminder"])
def test_rule_persistence_edit_removal_and_identity(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "series.db"
    base = datetime(2026, 9, 21, 9)
    data = (
        EventInput(
            title="Series", start_datetime=base, end_datetime=base.replace(hour=10)
        )
        if kind == "event"
        else ReminderInput(title="Series", reminder_datetime=base)
    )

    def service(engine: object) -> EventService | ReminderService:
        return (
            EventService(EventRepository(engine))
            if kind == "event"
            else ReminderService(ReminderRepository(engine))
        )

    engine = initialize_database(path)
    api = service(engine)
    original = getattr(api, f"create_{kind}")(
        replace(data, recurrence_rule="FREQ=DAILY")
    )
    assert original.recurrence_rule == "FREQ=DAILY;INTERVAL=1"
    engine.dispose()
    engine = initialize_database(path)
    try:
        api = service(engine)
        assert getattr(api, f"get_{kind}")(original.id) == original
        changed = getattr(api, f"update_{kind}")(
            original.id, replace(data, recurrence_rule="FREQ=WEEKLY;BYDAY=FR")
        )
        assert changed.id == original.id and changed.created_at == original.created_at
        assert changed.updated_at > original.updated_at
        assert changed.recurrence_rule == "FREQ=WEEKLY;INTERVAL=1;BYDAY=FR"
        with pytest.raises(InputValidationError):
            getattr(api, f"update_{kind}")(
                original.id, replace(data, recurrence_rule="FREQ=YEARLY")
            )
        assert getattr(api, f"get_{kind}")(original.id) == changed
        removed = getattr(api, f"update_{kind}")(original.id, data)
        assert removed.recurrence_rule is None
        assert removed.id == original.id and removed.created_at == original.created_at
        with engine.connect() as connection:
            assert (
                connection.scalar(text(f"SELECT recurrence_rule FROM {kind}s")) is None
            )
        with pytest.raises(InputValidationError):
            getattr(api, f"create_{kind}")(
                replace(data, recurrence_rule="FREQ=DAILY;INTERVAL=0")
            )
        assert len(getattr(api, f"list_{kind}s")()) == 1
    finally:
        engine.dispose()
