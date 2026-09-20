"""Validate Fixed Events and expose safe application operations to the UI."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from src.database.repositories import EventRepository
from src.models.event import Event, EventInput


class EventValidationError(ValueError):
    """User-correctable input error."""


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
    if not isinstance(start, datetime):
        raise EventValidationError("Start date and time are required.")
    if not isinstance(end, datetime):
        raise EventValidationError("End date and time are required.")
    if start.tzinfo is not None or end.tzinfo is not None:
        raise EventValidationError("Use local date and time without a timezone.")
    if end <= start:
        raise EventValidationError("End time must be later than start time.")


def _normalize(data: EventInput) -> EventInput:
    if not isinstance(data.title, str) or not data.title.strip():
        raise EventValidationError("Title must not be empty.")
    title = data.title.strip()
    if len(title) > 200:
        raise EventValidationError("Title must be 200 characters or fewer.")
    _validate_interval(data.start_datetime, data.end_datetime)
    for label, value in (
        ("Description", data.description),
        ("Category", data.category),
        ("Location", data.location),
    ):
        if not isinstance(value, str):
            raise EventValidationError(f"{label} must be text.")
    return EventInput(
        title=title,
        start_datetime=data.start_datetime,
        end_datetime=data.end_datetime,
        description=data.description.strip(),
        category=data.category.strip() or "Other",
        location=data.location.strip(),
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
