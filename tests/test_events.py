"""Fixed Event validation, CRUD, interval queries and durable persistence."""

import subprocess
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from src.database.db import check_database_health, initialize_database
from src.database.repositories import EventRepository
from src.models.event import EventInput
from src.services.event_service import (
    EventService,
    EventStorageError,
    EventValidationError,
)


def event_input(start_hour: int = 19, end_hour: int = 21) -> EventInput:
    return EventInput(
        title="Football Training",
        start_datetime=datetime(2026, 9, 25, start_hour),
        end_datetime=datetime(2026, 9, 25, end_hour),
    )


@pytest.fixture
def service(tmp_path: Path) -> Iterator[EventService]:
    engine = initialize_database(tmp_path / "planlayer.db")
    try:
        yield EventService(EventRepository(engine))
    finally:
        engine.dispose()


def test_create_normalizes_and_persists_every_field(service: EventService) -> None:
    data = replace(
        event_input(),
        title=" Football Training ",
        description=" Practice ",
        category=" Sport ",
        location=" Football Pitch ",
    )
    saved = service.create_event(data)
    assert saved.id > 0
    assert saved.title == "Football Training"
    assert saved.description == "Practice"
    assert saved.location == "Football Pitch"
    assert saved.category == "Sport"
    assert saved.start_datetime == data.start_datetime
    assert saved.end_datetime == data.end_datetime
    assert saved.created_at == saved.updated_at
    assert saved.created_at.tzinfo is None
    assert service.get_event(saved.id) == saved


@pytest.mark.parametrize("title", ["", "    ", "\t\n", "a" * 201, None])
def test_invalid_title_is_rejected(service: EventService, title: str) -> None:
    with pytest.raises(EventValidationError, match="Title"):
        service.create_event(replace(event_input(), title=title))
    assert service.list_events() == []


@pytest.mark.parametrize("start,end", [(12, 10), (10, 10)])
def test_invalid_interval_is_rejected(
    service: EventService, start: int, end: int
) -> None:
    with pytest.raises(EventValidationError, match="End time must be later"):
        service.create_event(event_input(start, end))
    assert service.list_events() == []


@pytest.mark.parametrize("field", ["start_datetime", "end_datetime"])
@pytest.mark.parametrize(
    "value", [None, "2026-09-25", datetime.fromisoformat("2026-09-25T19:00:00+08:00")]
)
def test_missing_or_nonlocal_datetimes_rejected(
    service: EventService, field: str, value: object
) -> None:
    with pytest.raises(EventValidationError):
        service.create_event(replace(event_input(), **{field: value}))
    assert service.list_events() == []


def test_default_category_and_max_title_length(service: EventService) -> None:
    saved = service.create_event(replace(event_input(), title="a" * 200, category="  "))
    assert saved.category == "Other"
    assert saved.description == saved.location == ""


def test_update_preserves_identity_and_refreshes_timestamp(
    service: EventService,
) -> None:
    original = service.create_event(event_input())
    data = replace(
        event_input(18, 20),
        title="Gym",
        description="Weights",
        location="Hall",
        category="Health",
    )
    updated = service.update_event(original.id, data)
    assert updated is not None
    assert updated.id == original.id
    assert updated.created_at == original.created_at
    assert updated.updated_at > original.updated_at
    for field in (
        "title",
        "description",
        "start_datetime",
        "end_datetime",
        "category",
        "location",
    ):
        assert getattr(updated, field) == getattr(data, field)
    assert service.get_event(original.id) == updated


def test_invalid_update_preserves_saved_data(service: EventService) -> None:
    saved = service.create_event(event_input())
    with pytest.raises(EventValidationError):
        service.update_event(saved.id, event_input(21, 19))
    assert service.get_event(saved.id) == saved


def test_delete_and_missing_ids_are_safe(service: EventService) -> None:
    assert service.get_event(999) is None
    assert service.update_event(999, event_input()) is None
    assert service.delete_event(999) is False
    saved = service.create_event(event_input())
    assert service.delete_event(saved.id) is True
    assert service.get_event(saved.id) is None
    assert service.delete_event(saved.id) is False
    assert service.list_events() == []


def test_list_events_is_chronological_with_stable_ties(service: EventService) -> None:
    for hour in (14, 9, 11, 9):
        service.create_event(event_input(hour, hour + 1))
    events = service.list_events()
    assert [event.start_datetime.hour for event in events] == [9, 9, 11, 14]
    assert events[0].id < events[1].id


def test_range_query_includes_partial_and_containing_overlaps(
    service: EventService,
) -> None:
    intervals = [
        (8, 0, 9, 0),
        (9, 30, 10, 30),
        (11, 0, 13, 0),
        (14, 0, 15, 0),
        (9, 0, 10, 0),
        (12, 0, 13, 0),
        (9, 0, 13, 0),
        (10, 0, 12, 0),
    ]
    saved = []
    for sh, sm, eh, em in intervals:
        saved.append(
            service.create_event(
                replace(
                    event_input(),
                    start_datetime=datetime(2026, 9, 25, sh, sm),
                    end_datetime=datetime(2026, 9, 25, eh, em),
                )
            )
        )
    matches = service.get_events_between(
        datetime(2026, 9, 25, 10), datetime(2026, 9, 25, 12)
    )
    assert [event.id for event in matches] == [saved[i].id for i in (6, 1, 7, 2)]


def test_range_includes_overnight_event(service: EventService) -> None:
    saved = service.create_event(
        replace(
            event_input(),
            start_datetime=datetime(2026, 9, 24, 23),
            end_datetime=datetime(2026, 9, 25, 2),
        )
    )
    assert service.get_events_between(
        datetime(2026, 9, 25), datetime(2026, 9, 25, 1)
    ) == [saved]


@pytest.mark.parametrize("start,end", [(12, 10), (10, 10)])
def test_invalid_query_range_is_rejected(
    service: EventService, start: int, end: int
) -> None:
    with pytest.raises(EventValidationError):
        service.get_events_between(
            datetime(2026, 9, 25, start), datetime(2026, 9, 25, end)
        )


def test_persistence_survives_a_new_process(tmp_path: Path) -> None:
    path = tmp_path / "planlayer.db"
    engine = initialize_database(path)
    service = EventService(EventRepository(engine))
    saved = service.create_event(event_input())
    engine.dispose()
    script = """
import sys
from pathlib import Path
from src.database.db import initialize_database
from src.database.repositories import EventRepository
engine = initialize_database(Path(sys.argv[1]))
try:
    event = EventRepository(engine).get_event(int(sys.argv[2]))
    assert event is not None
    assert event.title == 'Football Training'
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
    engine = initialize_database(path)
    try:
        assert check_database_health(engine)
        assert EventRepository(engine).get_event(saved.id) == saved
    finally:
        engine.dispose()


def test_database_constraints_and_rollback(tmp_path: Path) -> None:
    engine = initialize_database(tmp_path / "planlayer.db")
    repository = EventRepository(engine)
    try:
        with pytest.raises(IntegrityError):
            repository.create_event(event_input(12, 10))
        assert repository.list_events() == []
        assert repository.create_event(event_input()).id > 0
        assert inspect(engine).get_table_names() == ["events"]
    finally:
        engine.dispose()


def test_storage_failure_has_safe_application_message(tmp_path: Path) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{(tmp_path / 'missing' / 'db').as_posix()}")
    try:
        with pytest.raises(EventStorageError, match="Could not access saved events"):
            EventService(EventRepository(engine)).list_events()
    finally:
        engine.dispose()
