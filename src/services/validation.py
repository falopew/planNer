"""Small shared input rules; no scheduling or persistence behavior."""

from datetime import datetime


class InputValidationError(ValueError):
    """A user-correctable input error safe to display."""


def validate_title(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputValidationError("Title must not be empty.")
    title = value.strip()
    if len(title) > 200:
        raise InputValidationError("Title must be 200 characters or fewer.")
    return title


def validate_local_datetime(value: datetime | None, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise InputValidationError(f"{label} date and time are required.")
    if value.tzinfo is not None:
        raise InputValidationError("Use local date and time without a timezone.")
    return value


def normalize_text(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise InputValidationError(f"{label} must be text.")
    return value.strip()
