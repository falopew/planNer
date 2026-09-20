"""Reminder validation and operations, independent of occupied calendar time."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError

from src.database.reminder_repository import ReminderRepository
from src.models.reminder import Reminder, ReminderInput
from src.services.validation import (
    InputValidationError,
    normalize_text,
    validate_local_datetime,
    validate_title,
)

ReminderValidationError = InputValidationError


class ReminderStorageError(RuntimeError):
    """Safe message for a failed reminder operation."""


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except SQLAlchemyError as error:
        raise ReminderStorageError(
            "Could not access saved reminders. Please try again or check the database."
        ) from error


def _normalize(data: ReminderInput) -> ReminderInput:
    return ReminderInput(
        title=validate_title(data.title),
        reminder_datetime=validate_local_datetime(data.reminder_datetime, "Reminder"),
        description=normalize_text(data.description, "Description"),
        category=normalize_text(data.category, "Category") or "Other",
    )


class ReminderService:
    def __init__(self, repository: ReminderRepository) -> None:
        self._repository = repository

    def create_reminder(self, data: ReminderInput) -> Reminder:
        normalized = _normalize(data)
        with _storage_errors():
            return self._repository.create_reminder(normalized)

    def get_reminder(self, reminder_id: int) -> Reminder | None:
        with _storage_errors():
            return self._repository.get_reminder(reminder_id)

    def list_reminders(self) -> list[Reminder]:
        with _storage_errors():
            return self._repository.list_reminders()

    def get_reminders_between(self, start: datetime, end: datetime) -> list[Reminder]:
        start = validate_local_datetime(start, "Range start")
        end = validate_local_datetime(end, "Range end")
        if end <= start:
            raise ReminderValidationError("Range end must be later than range start.")
        with _storage_errors():
            return self._repository.get_reminders_between(start, end)

    def update_reminder(self, reminder_id: int, data: ReminderInput) -> Reminder | None:
        normalized = _normalize(data)
        with _storage_errors():
            return self._repository.update_reminder(reminder_id, normalized)

    def delete_reminder(self, reminder_id: int) -> bool:
        with _storage_errors():
            return self._repository.delete_reminder(reminder_id)
