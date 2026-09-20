"""Validate Fixed Events and expose safe application operations to the UI."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from src.database.repositories import EventRepository
from src.models.event import Event, EventInput
from src.services.validation import (
    InputValidationError,
    normalize_text,
    validate_local_datetime,
    validate_title,
)

EventValidationError = InputValidationError


class EventStorageError(RuntimeError):
    """Safe message for a failed persistence operation."""


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except SQLAlchemyError as error:
        raise EventStorageError(
            "Could not access saved events. Please try again or check the database."
        ) from error


def _validate_interval(start: datetime | None, end: datetime | None) -> None:
    start = validate_local_datetime(start, "Start")
    end = validate_local_datetime(end, "End")
    if end <= start:
        raise EventValidationError("End time must be later than start time.")


def _normalize(data: EventInput) -> EventInput:
    title = validate_title(data.title)
    _validate_interval(data.start_datetime, data.end_datetime)
    return EventInput(
        title=title,
        start_datetime=data.start_datetime,
        end_datetime=data.end_datetime,
        description=normalize_text(data.description, "Description"),
        category=normalize_text(data.category, "Category") or "Other",
        location=normalize_text(data.location, "Location"),
    )


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def create_event(self, data: EventInput) -> Event:
        normalized = _normalize(data)
        with _storage_errors():
            return self._repository.create_event(normalized)

    def get_event(self, event_id: int) -> Event | None:
        with _storage_errors():
            return self._repository.get_event(event_id)

    def list_events(self) -> list[Event]:
        with _storage_errors():
            return self._repository.list_events()

    def get_events_between(self, start: datetime, end: datetime) -> list[Event]:
        _validate_interval(start, end)
        with _storage_errors():
            return self._repository.get_events_between(start, end)

    def update_event(self, event_id: int, data: EventInput) -> Event | None:
        normalized = _normalize(data)
        with _storage_errors():
            return self._repository.update_event(event_id, normalized)

    def delete_event(self, event_id: int) -> bool:
        with _storage_errors():
            return self._repository.delete_event(event_id)
